from __future__ import annotations

import json
import os

# Tool names whose `input.file_path` names a file the model actually touched.
FILE_TOOL_NAMES = {"Edit", "MultiEdit", "Write", "Read", "NotebookEdit"}


def extract_tool_uses(response_body_raw: str | None, is_stream: bool) -> list[dict]:
    """Reconstruct completed tool_use blocks (id, name, input) from a stored response_body.

    Non-streaming bodies are the raw Anthropic Message JSON — content blocks are
    already complete. Streaming bodies are the list of raw SSE events the proxy
    persists; a tool_use block's `input` arrives as `input_json_delta` fragments
    keyed by content-block index and has to be reassembled here.
    """
    if not response_body_raw:
        return []
    try:
        data = json.loads(response_body_raw)
    except json.JSONDecodeError:
        return []

    if not is_stream:
        content = data.get("content", []) if isinstance(data, dict) else []
        return [
            {"id": b.get("id"), "name": b.get("name"), "input": b.get("input") or {}}
            for b in content
            if isinstance(b, dict) and b.get("type") == "tool_use"
        ]

    if not isinstance(data, list):
        return []

    blocks: dict[int, dict] = {}
    for event in data:
        etype = event.get("type")
        if etype == "content_block_start":
            block = event.get("content_block", {})
            if block.get("type") == "tool_use":
                blocks[event.get("index")] = {"id": block.get("id"), "name": block.get("name"), "json": ""}
        elif etype == "content_block_delta":
            idx = event.get("index")
            if idx in blocks:
                delta = event.get("delta", {})
                if delta.get("type") == "input_json_delta":
                    blocks[idx]["json"] += delta.get("partial_json", "")

    results = []
    for b in blocks.values():
        try:
            input_data = json.loads(b["json"]) if b["json"] else {}
        except json.JSONDecodeError:
            input_data = {}
        results.append({"id": b["id"], "name": b["name"], "input": input_data})
    return results


def folders_touched(response_body_raw: str | None, is_stream: bool) -> set[str]:
    """Distinct directories touched by file-oriented tool calls in one response."""
    folders = set()
    for tu in extract_tool_uses(response_body_raw, is_stream):
        if tu["name"] not in FILE_TOOL_NAMES:
            continue
        path = tu["input"].get("file_path")
        if not path:
            continue
        folders.add(os.path.dirname(path) or "/")
    return folders


def common_prefix(folders: list[str]) -> str:
    if not folders:
        return ""
    try:
        return os.path.commonpath(folders)
    except ValueError:
        return ""


def relativize(folder: str, prefix: str) -> str:
    if prefix and folder == prefix:
        return "."
    if prefix and folder.startswith(prefix.rstrip("/") + "/"):
        return folder[len(prefix.rstrip("/")) + 1 :]
    return folder
