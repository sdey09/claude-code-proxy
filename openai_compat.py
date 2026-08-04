"""Translation layer between OpenAI's Chat Completions API and Anthropic's Messages API.

Lets OpenAI-SDK clients (aider, LibreChat, custom scripts, ...) talk to this proxy at
/v1/chat/completions. Requests are translated to Anthropic's /v1/messages shape and sent
through the existing routing/forwarder/persistence pipeline unchanged; the Anthropic
response (JSON or SSE) is translated back to OpenAI's shape on the way out.
"""
from __future__ import annotations

import json
from typing import Optional

_STOP_REASON_MAP = {
    "end_turn": "stop",
    "stop_sequence": "stop",
    "tool_use": "tool_calls",
    "max_tokens": "length",
}

_ANTHROPIC_VERSION = "2023-06-01"


def _map_stop_reason(reason: Optional[str]) -> str:
    return _STOP_REASON_MAP.get(reason or "", "stop")


def _content_to_text(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text"
        )
    return str(content)


def _to_anthropic_user_content(content):
    if isinstance(content, str) or content is None:
        return content or ""
    blocks = []
    for part in content:
        ptype = part.get("type")
        if ptype == "text":
            blocks.append({"type": "text", "text": part.get("text", "")})
        elif ptype == "image_url":
            url = (part.get("image_url") or {}).get("url", "")
            if url.startswith("data:"):
                header, _, b64data = url.partition(",")
                media_type = header[len("data:"):].split(";")[0] or "image/png"
                blocks.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type, "data": b64data},
                })
            elif url:
                blocks.append({"type": "image", "source": {"type": "url", "url": url}})
    return blocks


def _to_anthropic_tool(tool: dict) -> dict:
    fn = tool.get("function", tool)
    return {
        "name": fn.get("name"),
        "description": fn.get("description", ""),
        "input_schema": fn.get("parameters") or {"type": "object", "properties": {}},
    }


def _to_anthropic_tool_choice(tool_choice):
    if isinstance(tool_choice, str):
        if tool_choice == "none":
            return {"type": "none"}
        if tool_choice == "required":
            return {"type": "any"}
        return {"type": "auto"}
    if isinstance(tool_choice, dict):
        fn = tool_choice.get("function", {})
        return {"type": "tool", "name": fn.get("name")}
    return {"type": "auto"}


def openai_to_anthropic_request(body: dict) -> dict:
    system_parts: list[str] = []
    messages: list[dict] = []

    for msg in body.get("messages") or []:
        role = msg.get("role")

        if role in ("system", "developer"):
            text = _content_to_text(msg.get("content"))
            if text:
                system_parts.append(text)
            continue

        if role == "tool":
            messages.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": msg.get("tool_call_id"),
                    "content": _content_to_text(msg.get("content")),
                }],
            })
            continue

        if role == "assistant":
            blocks = []
            text = msg.get("content")
            if text:
                blocks.append({"type": "text", "text": _content_to_text(text)})
            for tc in msg.get("tool_calls") or []:
                fn = tc.get("function", {})
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                blocks.append({
                    "type": "tool_use",
                    "id": tc.get("id"),
                    "name": fn.get("name"),
                    "input": args,
                })
            messages.append({"role": "assistant", "content": blocks})
            continue

        # user (and anything else, treated as user)
        messages.append({"role": "user", "content": _to_anthropic_user_content(msg.get("content"))})

    anthropic: dict = {
        "model": body.get("model"),
        "messages": messages,
        "max_tokens": body.get("max_tokens") or body.get("max_completion_tokens") or 4096,
    }
    if system_parts:
        anthropic["system"] = "\n\n".join(system_parts)
    if "temperature" in body:
        anthropic["temperature"] = body["temperature"]
    if "top_p" in body:
        anthropic["top_p"] = body["top_p"]
    if body.get("stream"):
        anthropic["stream"] = True

    stop = body.get("stop")
    if stop:
        anthropic["stop_sequences"] = [stop] if isinstance(stop, str) else stop

    tools = [t for t in (body.get("tools") or []) if t.get("type", "function") == "function"]
    if tools:
        anthropic["tools"] = [_to_anthropic_tool(t) for t in tools]

    if body.get("tool_choice") is not None:
        anthropic["tool_choice"] = _to_anthropic_tool_choice(body["tool_choice"])

    return anthropic


def anthropic_response_to_openai(data: dict, created: int) -> dict:
    content_text = ""
    tool_calls = []
    for block in data.get("content") or []:
        if block.get("type") == "text":
            content_text += block.get("text", "")
        elif block.get("type") == "tool_use":
            tool_calls.append({
                "id": block.get("id"),
                "type": "function",
                "function": {
                    "name": block.get("name"),
                    "arguments": json.dumps(block.get("input", {})),
                },
            })

    message: dict = {"role": "assistant", "content": content_text or None}
    if tool_calls:
        message["tool_calls"] = tool_calls

    usage = data.get("usage") or {}
    prompt_tokens = usage.get("input_tokens", 0)
    completion_tokens = usage.get("output_tokens", 0)

    return {
        "id": data.get("id") or "chatcmpl",
        "object": "chat.completion",
        "created": created,
        "model": data.get("model"),
        "choices": [{
            "index": 0,
            "message": message,
            "finish_reason": _map_stop_reason(data.get("stop_reason")),
        }],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


def anthropic_error_to_openai(raw_text: str) -> bytes:
    try:
        data = json.loads(raw_text)
        err = data.get("error", {})
        message = err.get("message", raw_text)
        etype = err.get("type", "api_error")
    except json.JSONDecodeError:
        message, etype = raw_text, "api_error"
    return json.dumps({"error": {"message": message, "type": etype, "code": None}}).encode()


def translate_auth_headers(headers: dict) -> None:
    """Mutates headers in place: OpenAI-style `Authorization: Bearer <key>` -> Anthropic's `x-api-key`,
    and ensures `anthropic-version` is set. Only call this for routes that pass client auth through."""
    if not any(k.lower() == "x-api-key" for k in headers):
        for k in list(headers.keys()):
            if k.lower() == "authorization":
                value = headers.pop(k)
                if value.lower().startswith("bearer "):
                    headers["x-api-key"] = value[7:].strip()
                break
    if not any(k.lower() == "anthropic-version" for k in headers):
        headers["anthropic-version"] = _ANTHROPIC_VERSION


class OpenAIStreamTranslator:
    """Incrementally translates an Anthropic SSE byte stream into OpenAI chat.completion.chunk SSE bytes."""

    def __init__(self, model: str, created: int, include_usage: bool = False) -> None:
        self.model = model
        self.created = created
        self.include_usage = include_usage
        self.id: Optional[str] = None
        self.prompt_tokens = 0
        self.finish_reason: Optional[str] = None
        self.usage: Optional[dict] = None
        self._buf = b""
        self._tool_call_index: dict[int, int] = {}
        self._next_tool_call_index = 0

    def feed(self, chunk: bytes) -> bytes:
        self._buf += chunk
        out = []
        while b"\n\n" in self._buf:
            raw_event, self._buf = self._buf.split(b"\n\n", 1)
            out.append(self._process_event(raw_event))
        return b"".join(out)

    def _process_event(self, raw_event: bytes) -> bytes:
        data_line = None
        for line in raw_event.decode(errors="replace").splitlines():
            if line.startswith("data:"):
                data_line = line[len("data:"):].strip()
        if not data_line:
            return b""
        try:
            event = json.loads(data_line)
        except json.JSONDecodeError:
            return b""
        return self._translate(event)

    def _chunk(self, delta: dict, finish_reason: Optional[str] = None) -> bytes:
        obj = {
            "id": self.id or "chatcmpl",
            "object": "chat.completion.chunk",
            "created": self.created,
            "model": self.model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
        }
        return f"data: {json.dumps(obj)}\n\n".encode()

    def _usage_chunk(self) -> bytes:
        obj = {
            "id": self.id or "chatcmpl",
            "object": "chat.completion.chunk",
            "created": self.created,
            "model": self.model,
            "choices": [],
            "usage": self.usage,
        }
        return f"data: {json.dumps(obj)}\n\n".encode()

    def _translate(self, event: dict) -> bytes:
        etype = event.get("type")
        parts: list[bytes] = []

        if etype == "message_start":
            msg = event.get("message", {})
            self.id = msg.get("id")
            self.model = msg.get("model", self.model)
            self.prompt_tokens = (msg.get("usage") or {}).get("input_tokens", 0)
            parts.append(self._chunk(delta={"role": "assistant", "content": ""}))

        elif etype == "content_block_start":
            block = event.get("content_block", {})
            idx = event.get("index", 0)
            if block.get("type") == "tool_use":
                oi = self._next_tool_call_index
                self._next_tool_call_index += 1
                self._tool_call_index[idx] = oi
                parts.append(self._chunk(delta={
                    "tool_calls": [{
                        "index": oi,
                        "id": block.get("id"),
                        "type": "function",
                        "function": {"name": block.get("name"), "arguments": ""},
                    }],
                }))

        elif etype == "content_block_delta":
            idx = event.get("index", 0)
            delta = event.get("delta", {})
            dtype = delta.get("type")
            if dtype == "text_delta":
                parts.append(self._chunk(delta={"content": delta.get("text", "")}))
            elif dtype == "input_json_delta":
                oi = self._tool_call_index.get(idx, 0)
                parts.append(self._chunk(delta={
                    "tool_calls": [{"index": oi, "function": {"arguments": delta.get("partial_json", "")}}],
                }))

        elif etype == "message_delta":
            delta = event.get("delta", {})
            if "stop_reason" in delta:
                self.finish_reason = _map_stop_reason(delta["stop_reason"])
            usage = event.get("usage") or {}
            if usage:
                completion_tokens = usage.get("output_tokens", 0)
                self.usage = {
                    "prompt_tokens": self.prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": self.prompt_tokens + completion_tokens,
                }

        elif etype == "message_stop":
            parts.append(self._chunk(delta={}, finish_reason=self.finish_reason or "stop"))
            if self.include_usage and self.usage:
                parts.append(self._usage_chunk())
            parts.append(b"data: [DONE]\n\n")

        elif etype == "error":
            err = event.get("error", {})
            parts.append(
                f"data: {json.dumps({'error': {'message': err.get('message', 'upstream error'), 'type': err.get('type', 'api_error')}})}\n\n".encode()
            )
            parts.append(b"data: [DONE]\n\n")

        return b"".join(parts)
