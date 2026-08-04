"""Translation layer between OpenAI's Chat Completions API and Anthropic's Messages API.

Lets OpenAI-SDK clients (aider, LibreChat, custom scripts, ...) talk to this proxy at
/v1/chat/completions. Requests are translated to Anthropic's /v1/messages shape and sent
through the existing routing/forwarder/persistence pipeline unchanged; the Anthropic
response (JSON or SSE) is translated back to OpenAI's shape on the way out.
"""
from __future__ import annotations

import json
from typing import Optional

from sse_accumulator import ParsedResponse

_STOP_REASON_MAP = {
    "end_turn": "stop",
    "stop_sequence": "stop",
    "tool_use": "tool_calls",
    "max_tokens": "length",
}

_OPENAI_FINISH_TO_ANTHROPIC = {
    "stop": "end_turn",
    "length": "max_tokens",
    "tool_calls": "tool_use",
    "content_filter": "end_turn",
}

_ANTHROPIC_VERSION = "2023-06-01"


def _map_stop_reason(reason: Optional[str]) -> str:
    return _STOP_REASON_MAP.get(reason or "", "stop")


def _map_finish_reason(reason: Optional[str]) -> str:
    return _OPENAI_FINISH_TO_ANTHROPIC.get(reason or "", "end_turn")


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


def _anthropic_content_blocks(content) -> list:
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if isinstance(content, list):
        return content
    return []


def anthropic_messages_to_openai(messages: list[dict], system) -> list[dict]:
    openai_messages: list[dict] = []

    if system:
        system_text = system if isinstance(system, str) else _content_to_text(system)
        if system_text:
            openai_messages.append({"role": "system", "content": system_text})

    for msg in messages:
        role = msg.get("role")
        blocks = _anthropic_content_blocks(msg.get("content"))

        if role == "assistant":
            text_parts = []
            tool_calls = []
            for b in blocks:
                btype = b.get("type")
                if btype == "text":
                    text_parts.append(b.get("text", ""))
                elif btype == "tool_use":
                    tool_calls.append({
                        "id": b.get("id"),
                        "type": "function",
                        "function": {"name": b.get("name"), "arguments": json.dumps(b.get("input", {}))},
                    })
            om: dict = {"role": "assistant", "content": "".join(text_parts) or None}
            if tool_calls:
                om["tool_calls"] = tool_calls
            openai_messages.append(om)
            continue

        # user (and anything else, treated as user)
        content_parts: list[dict] = []
        for b in blocks:
            btype = b.get("type")
            if btype == "tool_result":
                if content_parts:
                    openai_messages.append({"role": "user", "content": content_parts})
                    content_parts = []
                openai_messages.append({
                    "role": "tool",
                    "tool_call_id": b.get("tool_use_id"),
                    "content": _content_to_text(b.get("content")),
                })
            elif btype == "text":
                content_parts.append({"type": "text", "text": b.get("text", "")})
            elif btype == "image":
                source = b.get("source", {})
                if source.get("type") == "base64":
                    url = f"data:{source.get('media_type', 'image/png')};base64,{source.get('data', '')}"
                else:
                    url = source.get("url", "")
                content_parts.append({"type": "image_url", "image_url": {"url": url}})
        if content_parts:
            openai_messages.append({"role": "user", "content": content_parts})

    return openai_messages


def _to_openai_tool(t: dict) -> dict:
    return {
        "type": "function",
        "function": {
            "name": t.get("name"),
            "description": t.get("description", ""),
            "parameters": t.get("input_schema") or {"type": "object", "properties": {}},
        },
    }


def _to_openai_tool_choice(tool_choice: dict):
    ttype = tool_choice.get("type")
    if ttype == "none":
        return "none"
    if ttype == "any":
        return "required"
    if ttype == "tool":
        return {"type": "function", "function": {"name": tool_choice.get("name")}}
    return "auto"


def anthropic_to_openai_request(body: dict) -> dict:
    openai: dict = {
        "model": body.get("model"),
        "messages": anthropic_messages_to_openai(body.get("messages") or [], body.get("system")),
    }
    if "max_tokens" in body:
        openai["max_tokens"] = body["max_tokens"]
    if "temperature" in body:
        openai["temperature"] = body["temperature"]
    if "top_p" in body:
        openai["top_p"] = body["top_p"]
    if body.get("stream"):
        openai["stream"] = True
        # OpenAI-compatible APIs only report token usage in-band via this flag; we need it
        # for both the Anthropic message_delta.usage we hand back and for cost persistence.
        openai["stream_options"] = {"include_usage": True}

    stop_sequences = body.get("stop_sequences")
    if stop_sequences:
        openai["stop"] = stop_sequences

    tools = body.get("tools")
    if tools:
        openai["tools"] = [_to_openai_tool(t) for t in tools]

    if body.get("tool_choice") is not None:
        openai["tool_choice"] = _to_openai_tool_choice(body["tool_choice"])

    return openai


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


def openai_response_to_anthropic(data: dict) -> dict:
    choice = (data.get("choices") or [{}])[0]
    message = choice.get("message") or {}

    blocks: list[dict] = []
    text = message.get("content")
    if text:
        blocks.append({"type": "text", "text": text})
    for tc in message.get("tool_calls") or []:
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

    usage = data.get("usage") or {}

    return {
        "id": data.get("id") or "msg",
        "type": "message",
        "role": "assistant",
        "model": data.get("model"),
        "content": blocks,
        "stop_reason": _map_finish_reason(choice.get("finish_reason")),
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        },
    }


def openai_error_to_anthropic(raw_text: str) -> bytes:
    try:
        data = json.loads(raw_text)
        err = data.get("error", {})
        message = err.get("message", raw_text)
        etype = err.get("type", "api_error")
    except json.JSONDecodeError:
        message, etype = raw_text, "api_error"
    return json.dumps({"type": "error", "error": {"type": etype, "message": message}}).encode()


def translate_auth_headers_to_openai(headers: dict) -> None:
    """Mutates headers in place: Anthropic-style `x-api-key: <key>` -> OpenAI's
    `Authorization: Bearer <key>`. Only call this for routes that pass client auth through."""
    if any(k.lower() == "authorization" for k in headers):
        return
    for k in list(headers.keys()):
        if k.lower() == "x-api-key":
            value = headers.pop(k)
            headers["Authorization"] = f"Bearer {value}"
            break


def parse_openai_json_response(body: bytes) -> ParsedResponse:
    """Parse a non-streaming OpenAI-shaped response body into the common ParsedResponse shape."""
    result = ParsedResponse()
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return result

    result.request_id = data.get("id")
    result.model = data.get("model")

    choice = (data.get("choices") or [{}])[0]
    result.stop_reason = _map_finish_reason(choice.get("finish_reason"))
    message = choice.get("message") or {}
    result.content_text = message.get("content") or ""

    usage = data.get("usage") or {}
    result.input_tokens = usage.get("prompt_tokens", 0)
    result.output_tokens = usage.get("completion_tokens", 0)

    return result


def parse_openai_sse_buffer(raw: bytes) -> ParsedResponse:
    """Parse accumulated OpenAI chat.completion.chunk SSE bytes into the common ParsedResponse shape."""
    result = ParsedResponse()
    text_parts: list[str] = []

    for line in raw.decode(errors="replace").splitlines():
        if not line.startswith("data:"):
            continue
        payload = line[len("data:"):].strip()
        if payload == "[DONE]":
            break
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            continue

        result.raw_events.append(event)

        if event.get("id"):
            result.request_id = event["id"]
        if event.get("model"):
            result.model = event["model"]

        usage = event.get("usage")
        if usage:
            result.input_tokens = usage.get("prompt_tokens", result.input_tokens)
            result.output_tokens = usage.get("completion_tokens", result.output_tokens)

        for choice in event.get("choices") or []:
            delta = choice.get("delta") or {}
            if delta.get("content"):
                text_parts.append(delta["content"])
            if choice.get("finish_reason"):
                result.stop_reason = _map_finish_reason(choice["finish_reason"])

    result.content_text = "".join(text_parts)
    return result


class AnthropicStreamTranslator:
    """Incrementally translates an OpenAI chat.completion.chunk SSE byte stream into
    Anthropic Messages SSE bytes.

    Known fidelity gap: OpenAI-compatible APIs only report token usage once, at the end of
    the stream (via stream_options.include_usage) - so the message_start event emitted here
    reports input_tokens=0. Accurate input/output token counts are still captured separately
    for persistence via parse_openai_sse_buffer, which reads the raw upstream bytes directly.
    """

    def __init__(self, model: str) -> None:
        self.model = model
        self.id: Optional[str] = None
        self._buf = b""
        self._started = False
        self._text_block_open = False
        self._tool_block_index: dict[int, int] = {}
        self._next_block_index = 0
        self._finish_reason: Optional[str] = None
        self._prompt_tokens = 0
        self._completion_tokens = 0
        self._stopped = False

    def feed(self, chunk: bytes) -> bytes:
        self._buf += chunk
        out = []
        while b"\n\n" in self._buf:
            raw_event, self._buf = self._buf.split(b"\n\n", 1)
            out.append(self._process_event(raw_event))
        return b"".join(out)

    def _event(self, etype: str, data: dict) -> bytes:
        return f"event: {etype}\ndata: {json.dumps(data)}\n\n".encode()

    def _ensure_started(self) -> bytes:
        if self._started:
            return b""
        self._started = True
        return self._event("message_start", {
            "type": "message_start",
            "message": {
                "id": self.id or "msg",
                "type": "message",
                "role": "assistant",
                "model": self.model,
                "content": [],
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {"input_tokens": self._prompt_tokens, "output_tokens": 0},
            },
        })

    def _process_event(self, raw_event: bytes) -> bytes:
        data_line = None
        for line in raw_event.decode(errors="replace").splitlines():
            if line.startswith("data:"):
                data_line = line[len("data:"):].strip()
        if data_line is None:
            return b""
        if data_line == "[DONE]":
            return self._finish()
        try:
            event = json.loads(data_line)
        except json.JSONDecodeError:
            return b""
        return self._translate(event)

    def _translate(self, event: dict) -> bytes:
        parts: list[bytes] = []

        if event.get("id"):
            self.id = event["id"]
        if event.get("model"):
            self.model = event["model"]

        usage = event.get("usage")
        if usage:
            self._prompt_tokens = usage.get("prompt_tokens", self._prompt_tokens)
            self._completion_tokens = usage.get("completion_tokens", self._completion_tokens)

        parts.append(self._ensure_started())

        for choice in event.get("choices") or []:
            delta = choice.get("delta") or {}

            if delta.get("content"):
                if not self._text_block_open:
                    self._text_block_open = True
                    idx = self._next_block_index
                    self._next_block_index += 1
                    self._text_block_idx = idx
                    parts.append(self._event("content_block_start", {
                        "type": "content_block_start", "index": idx,
                        "content_block": {"type": "text", "text": ""},
                    }))
                parts.append(self._event("content_block_delta", {
                    "type": "content_block_delta", "index": self._text_block_idx,
                    "delta": {"type": "text_delta", "text": delta["content"]},
                }))

            for tc in delta.get("tool_calls") or []:
                oi = tc.get("index", 0)
                if oi not in self._tool_block_index:
                    if self._text_block_open:
                        parts.append(self._event("content_block_stop", {
                            "type": "content_block_stop", "index": self._text_block_idx,
                        }))
                        self._text_block_open = False
                    idx = self._next_block_index
                    self._next_block_index += 1
                    self._tool_block_index[oi] = idx
                    fn = tc.get("function", {})
                    parts.append(self._event("content_block_start", {
                        "type": "content_block_start", "index": idx,
                        "content_block": {"type": "tool_use", "id": tc.get("id"), "name": fn.get("name"), "input": {}},
                    }))
                idx = self._tool_block_index[oi]
                fn = tc.get("function", {})
                if fn.get("arguments"):
                    parts.append(self._event("content_block_delta", {
                        "type": "content_block_delta", "index": idx,
                        "delta": {"type": "input_json_delta", "partial_json": fn["arguments"]},
                    }))

            if choice.get("finish_reason"):
                self._finish_reason = _map_finish_reason(choice["finish_reason"])

        return b"".join(parts)

    def _finish(self) -> bytes:
        if self._stopped:
            return b""
        self._stopped = True
        parts: list[bytes] = []
        parts.append(self._ensure_started())

        if self._text_block_open:
            parts.append(self._event("content_block_stop", {
                "type": "content_block_stop", "index": self._text_block_idx,
            }))
        for idx in self._tool_block_index.values():
            parts.append(self._event("content_block_stop", {
                "type": "content_block_stop", "index": idx,
            }))

        parts.append(self._event("message_delta", {
            "type": "message_delta",
            "delta": {"stop_reason": self._finish_reason or "end_turn", "stop_sequence": None},
            "usage": {"output_tokens": self._completion_tokens},
        }))
        parts.append(self._event("message_stop", {"type": "message_stop"}))
        return b"".join(parts)


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
