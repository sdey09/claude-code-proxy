from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ParsedResponse:
    request_id: Optional[str] = None
    model: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    stop_reason: Optional[str] = None
    content_text: str = ""
    raw_events: list[dict] = field(default_factory=list)


def parse_sse_buffer(raw: bytes) -> ParsedResponse:
    """Parse accumulated SSE bytes into a structured response."""
    result = ParsedResponse()
    text_parts: list[str] = []

    for line in raw.decode(errors="replace").splitlines():
        if not line.startswith("data: "):
            continue
        payload = line[6:].strip()
        if payload == "[DONE]":
            break
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            continue

        result.raw_events.append(event)
        etype = event.get("type", "")

        if etype == "message_start":
            msg = event.get("message", {})
            result.request_id = msg.get("id")
            result.model = msg.get("model")
            usage = msg.get("usage", {})
            result.input_tokens = usage.get("input_tokens", 0)
            result.cache_write_tokens = usage.get("cache_creation_input_tokens", 0)
            result.cache_read_tokens = usage.get("cache_read_input_tokens", 0)

        elif etype == "content_block_delta":
            delta = event.get("delta", {})
            if delta.get("type") == "text_delta":
                text_parts.append(delta.get("text", ""))

        elif etype == "message_delta":
            usage = event.get("usage", {})
            result.output_tokens = usage.get("output_tokens", result.output_tokens)
            delta = event.get("delta", {})
            if "stop_reason" in delta:
                result.stop_reason = delta["stop_reason"]

    result.content_text = "".join(text_parts)
    return result


def parse_json_response(body: bytes) -> ParsedResponse:
    """Parse a non-streaming (JSON) response body."""
    result = ParsedResponse()
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return result

    result.request_id = data.get("id")
    result.model = data.get("model")
    result.stop_reason = data.get("stop_reason")

    usage = data.get("usage", {})
    result.input_tokens = usage.get("input_tokens", 0)
    result.output_tokens = usage.get("output_tokens", 0)
    result.cache_write_tokens = usage.get("cache_creation_input_tokens", 0)
    result.cache_read_tokens = usage.get("cache_read_input_tokens", 0)

    for block in data.get("content", []):
        if block.get("type") == "text":
            result.content_text += block.get("text", "")

    return result
