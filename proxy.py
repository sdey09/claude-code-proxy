# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "flask>=3.0",
#   "requests>=2.31",
#   "psycopg2-binary>=2.9",
#   "pyyaml>=6.0",
# ]
# ///
from __future__ import annotations

import atexit
import gzip
import json
import logging
import time
import zlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Optional

import requests
from flask import Flask, Response, redirect, request, stream_with_context, url_for

import db
from config import Config
from cost import estimate_cost, known_models
from dashboard import dashboard_bp
from db import RequestRecord
from forwarder import Forwarder, filter_headers
from openai_compat import (
    OpenAIStreamTranslator,
    anthropic_error_to_openai,
    anthropic_response_to_openai,
    openai_to_anthropic_request,
    translate_auth_headers,
)
from routing import load_routes, resolve_route
from sse_accumulator import ParsedResponse, parse_json_response, parse_sse_buffer

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="persist")


def _decompress(raw: bytes, content_encoding: str) -> bytes:
    """Decompress a response body for logging; the raw bytes are forwarded to the client untouched."""
    try:
        if content_encoding == "gzip":
            return gzip.decompress(raw)
        if content_encoding == "deflate":
            return zlib.decompress(raw, -zlib.MAX_WBITS)
    except (OSError, zlib.error) as exc:
        logger.warning("failed to decompress %s response body for logging: %s", content_encoding, exc)
    return raw


def _persist(
    cfg: Config,
    pool,
    timestamp_utc: str,
    path: str,
    is_stream: bool,
    is_sse_response: bool,
    request_body: bytes,
    request_json: Optional[dict],
    raw_buffer: list[bytes],
    content_encoding: str,
    status: int,
    ttfb_s: Optional[float],
    total_s: float,
    error_body: Optional[str],
) -> None:
    full_raw = _decompress(b"".join(raw_buffer), content_encoding)

    if is_sse_response:
        parsed: ParsedResponse = parse_sse_buffer(full_raw)
        response_body_str = json.dumps(parsed.raw_events)
    else:
        parsed = parse_json_response(full_raw)
        response_body_str = full_raw.decode(errors="replace") if full_raw else None

    model = parsed.model
    if not model and request_json:
        model = request_json.get("model")

    cost = estimate_cost(
        model=model or "unknown",
        input_tokens=parsed.input_tokens,
        output_tokens=parsed.output_tokens,
        cache_write_tokens=parsed.cache_write_tokens,
        cache_read_tokens=parsed.cache_read_tokens,
    )

    rec = RequestRecord(
        request_id=parsed.request_id,
        timestamp_utc=timestamp_utc,
        model=model,
        path=path,
        stream=is_stream,
        ttfb_s=ttfb_s,
        total_s=total_s,
        input_tokens=parsed.input_tokens,
        output_tokens=parsed.output_tokens,
        cache_write_tokens=parsed.cache_write_tokens,
        cache_read_tokens=parsed.cache_read_tokens,
        cost_usd=cost,
        stop_reason=parsed.stop_reason,
        request_body=request_body.decode(errors="replace") if request_body else None,
        response_body=response_body_str,
        error_body=error_body,
        status_code=status,
    )

    db.insert_record(pool, rec, cfg.max_body_store_bytes)

    logger.info(
        "✓ DONE  %-4s  status=%d  model=%-30s  in=%-6d out=%-6d  cost=$%.6f  total=%.2fs  ttfb=%.3fs",
        "SSE" if is_sse_response else "JSON",
        status,
        model or "?",
        parsed.input_tokens,
        parsed.output_tokens,
        cost,
        total_s,
        ttfb_s or 0,
    )


def _handle(app: Flask, path: str) -> Response:
    cfg: Config = app.config["cfg"]
    fwd: Forwarder = app.forwarder
    pool = app.db_pool

    timestamp_utc = datetime.now(timezone.utc).isoformat()
    body = request.get_data()

    request_json: Optional[dict] = None
    try:
        request_json = json.loads(body) if body else None
    except json.JSONDecodeError:
        pass

    is_stream = bool(request_json and request_json.get("stream", False))
    full_path = "/" + path
    if request.query_string:
        full_path += "?" + request.query_string.decode()
    model_hint = (request_json or {}).get("model", "?")

    try:
        route = resolve_route(app.routes, model_hint)
    except RuntimeError as exc:
        logger.error("✗ ROUTING FAILED: %s", exc)
        return Response(str(exc), status=502)

    logger.info(
        "── REQUEST  %s %s  model=%s  upstream=%s(%s)  stream=%s  body=%db",
        request.method, full_path, model_hint, route.type, route.base_url, is_stream, len(body),
    )

    t_start = time.monotonic()
    headers = filter_headers(request.headers)
    headers["content-length"] = str(len(body))
    upstream_url = route.base_url.rstrip("/") + full_path

    try:
        upstream = fwd.forward(request.method, upstream_url, headers, body, route)
    except RuntimeError as exc:
        logger.error("✗ ROUTING FAILED: %s", exc)
        return Response(str(exc), status=502)
    except requests.RequestException as exc:
        logger.error("✗ UPSTREAM CONNECT FAILED: %s", exc)
        return Response(str(exc), status=502)

    status = upstream.status_code
    resp_headers = Forwarder.response_headers(upstream)

    content_type = upstream.headers.get("content-type", "")
    content_encoding = upstream.headers.get("content-encoding", "")
    is_sse_response = "text/event-stream" in content_type

    logger.info("── UPSTREAM  status=%d  content-type=%s", status, content_type)
    if status >= 400:
        logger.warning("✗ UPSTREAM ERROR  status=%d  path=%s", status, full_path)

    state: dict = {"ttfb_s": None, "raw_buffer": [], "error_body": None}

    def generate():
        # decode_content=False: forward compressed bytes through untouched (matches the
        # original aiohttp auto_decompress=False behavior). requests/urllib3 otherwise
        # auto-decompresses on .content/.iter_content() while we still forward the
        # upstream's original Content-Encoding header, which corrupts the client's decode.
        if is_sse_response:
            for chunk in upstream.raw.stream(8192, decode_content=False):
                if not chunk:
                    continue
                if state["ttfb_s"] is None:
                    state["ttfb_s"] = time.monotonic() - t_start
                    logger.info("── FIRST BYTE  ttfb=%.3fs", state["ttfb_s"])
                state["raw_buffer"].append(chunk)
                yield chunk
        else:
            raw_response = upstream.raw.read(decode_content=False)
            state["ttfb_s"] = time.monotonic() - t_start
            state["raw_buffer"].append(raw_response)
            if status >= 400:
                state["error_body"] = _decompress(raw_response, content_encoding).decode(errors="replace")
                logger.error("✗ ERROR BODY: %s", state["error_body"][:500])
            yield raw_response

        total_s = time.monotonic() - t_start
        _executor.submit(
            _persist,
            cfg=cfg,
            pool=pool,
            timestamp_utc=timestamp_utc,
            path=full_path,
            is_stream=is_stream,
            is_sse_response=is_sse_response,
            request_body=body,
            request_json=request_json,
            raw_buffer=state["raw_buffer"],
            content_encoding=content_encoding,
            status=status,
            ttfb_s=state["ttfb_s"],
            total_s=total_s,
            error_body=state["error_body"],
        )

    return Response(stream_with_context(generate()), status=status, headers=resp_headers)


def _handle_openai(app: Flask) -> Response:
    """OpenAI-Chat-Completions-compatible entry point. Translates to Anthropic's /v1/messages
    shape, forwards through the same routing/persistence pipeline as _handle, and translates
    the Anthropic response back to OpenAI's shape."""
    cfg: Config = app.config["cfg"]
    fwd: Forwarder = app.forwarder
    pool = app.db_pool

    timestamp_utc = datetime.now(timezone.utc).isoformat()
    body = request.get_data()

    try:
        openai_json = json.loads(body) if body else {}
    except json.JSONDecodeError:
        return Response(
            json.dumps({"error": {"message": "invalid JSON body", "type": "invalid_request_error"}}),
            status=400, mimetype="application/json",
        )

    try:
        anthropic_json = openai_to_anthropic_request(openai_json)
    except Exception as exc:
        logger.exception("openai→anthropic request translation failed")
        return Response(
            json.dumps({"error": {"message": str(exc), "type": "invalid_request_error"}}),
            status=400, mimetype="application/json",
        )

    anthropic_body = json.dumps(anthropic_json).encode()
    is_stream = bool(anthropic_json.get("stream"))
    include_usage = bool((openai_json.get("stream_options") or {}).get("include_usage"))
    model_hint = anthropic_json.get("model") or "?"
    full_path = "/v1/chat/completions"

    try:
        route = resolve_route(app.routes, model_hint)
    except RuntimeError as exc:
        logger.error("✗ ROUTING FAILED: %s", exc)
        return Response(
            json.dumps({"error": {"message": str(exc), "type": "invalid_request_error"}}),
            status=502, mimetype="application/json",
        )

    logger.info(
        "── REQUEST  POST %s (openai-compat)  model=%s  upstream=%s(%s)  stream=%s  body=%db",
        full_path, model_hint, route.type, route.base_url, is_stream, len(anthropic_body),
    )

    t_start = time.monotonic()
    headers = filter_headers(request.headers)
    if not route.api_key_env:
        translate_auth_headers(headers)
    headers["content-type"] = "application/json"
    headers["content-length"] = str(len(anthropic_body))
    upstream_url = route.base_url.rstrip("/") + "/v1/messages"

    try:
        upstream = fwd.forward("POST", upstream_url, headers, anthropic_body, route)
    except RuntimeError as exc:
        logger.error("✗ ROUTING FAILED: %s", exc)
        return Response(
            json.dumps({"error": {"message": str(exc), "type": "api_error"}}),
            status=502, mimetype="application/json",
        )
    except requests.RequestException as exc:
        logger.error("✗ UPSTREAM CONNECT FAILED: %s", exc)
        return Response(
            json.dumps({"error": {"message": str(exc), "type": "api_error"}}),
            status=502, mimetype="application/json",
        )

    status = upstream.status_code
    content_type = upstream.headers.get("content-type", "")
    content_encoding = upstream.headers.get("content-encoding", "")
    is_sse_response = "text/event-stream" in content_type

    logger.info("── UPSTREAM  status=%d  content-type=%s", status, content_type)

    created = int(time.time())
    state: dict = {"ttfb_s": None, "raw_buffer": []}

    if status >= 400:
        raw_response = upstream.raw.read(decode_content=False)
        state["ttfb_s"] = time.monotonic() - t_start
        state["raw_buffer"].append(raw_response)
        error_text = _decompress(raw_response, content_encoding).decode(errors="replace")
        logger.warning("✗ UPSTREAM ERROR  status=%d  path=%s", status, full_path)
        logger.error("✗ ERROR BODY: %s", error_text[:500])
        total_s = time.monotonic() - t_start
        _executor.submit(
            _persist, cfg=cfg, pool=pool, timestamp_utc=timestamp_utc, path=full_path,
            is_stream=is_stream, is_sse_response=False, request_body=anthropic_body,
            request_json=anthropic_json, raw_buffer=state["raw_buffer"], content_encoding=content_encoding,
            status=status, ttfb_s=state["ttfb_s"], total_s=total_s, error_body=error_text,
        )
        return Response(anthropic_error_to_openai(error_text), status=status, mimetype="application/json")

    if is_sse_response:
        translator = OpenAIStreamTranslator(model=model_hint, created=created, include_usage=include_usage)

        def generate():
            for chunk in upstream.raw.stream(8192, decode_content=False):
                if not chunk:
                    continue
                if state["ttfb_s"] is None:
                    state["ttfb_s"] = time.monotonic() - t_start
                    logger.info("── FIRST BYTE  ttfb=%.3fs", state["ttfb_s"])
                state["raw_buffer"].append(chunk)
                out = translator.feed(chunk)
                if out:
                    yield out

            total_s = time.monotonic() - t_start
            _executor.submit(
                _persist, cfg=cfg, pool=pool, timestamp_utc=timestamp_utc, path=full_path,
                is_stream=True, is_sse_response=True, request_body=anthropic_body,
                request_json=anthropic_json, raw_buffer=state["raw_buffer"], content_encoding=content_encoding,
                status=status, ttfb_s=state["ttfb_s"], total_s=total_s, error_body=None,
            )

        return Response(
            stream_with_context(generate()), status=status, mimetype="text/event-stream",
            headers={"cache-control": "no-cache"},
        )

    raw_response = upstream.raw.read(decode_content=False)
    state["ttfb_s"] = time.monotonic() - t_start
    state["raw_buffer"].append(raw_response)
    total_s = time.monotonic() - t_start
    full_raw = _decompress(raw_response, content_encoding)
    try:
        openai_resp = anthropic_response_to_openai(json.loads(full_raw), created)
        out_body = json.dumps(openai_resp).encode()
    except json.JSONDecodeError:
        out_body = full_raw

    _executor.submit(
        _persist, cfg=cfg, pool=pool, timestamp_utc=timestamp_utc, path=full_path,
        is_stream=False, is_sse_response=False, request_body=anthropic_body,
        request_json=anthropic_json, raw_buffer=state["raw_buffer"], content_encoding=content_encoding,
        status=status, ttfb_s=state["ttfb_s"], total_s=total_s, error_body=None,
    )
    return Response(out_body, status=status, mimetype="application/json")


def create_app(cfg: Config) -> Flask:
    app = Flask(__name__)
    app.config["cfg"] = cfg

    app.db_pool = db.get_pool(cfg.database_url)
    db.init_db(app.db_pool)

    app.forwarder = Forwarder(cfg)
    app.routes = load_routes(cfg.upstream_routes_file)

    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")

    @app.route("/")
    def index():
        return redirect(url_for("dashboard.requests_view"))

    @app.route("/v1/chat/completions", methods=["POST"])
    def openai_chat_completions():
        return _handle_openai(app)

    @app.route("/v1/models", methods=["GET"])
    def openai_list_models():
        now = int(time.time())
        data = [{"id": name, "object": "model", "created": now, "owned_by": "anthropic"} for name in known_models()]
        return Response(json.dumps({"object": "list", "data": data}), mimetype="application/json")

    @app.route("/<path:path>", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    def proxy_handler(path):
        return _handle(app, path)

    def _shutdown():
        app.forwarder.close()
        db.close_pool(app.db_pool)

    atexit.register(_shutdown)

    logger.info("=" * 60)
    logger.info("  claude-mitm-proxy  READY")
    logger.info("  Listening  : http://0.0.0.0:%d", cfg.proxy_port)
    logger.info("  Routes     : %s", cfg.upstream_routes_file)
    for route in app.routes:
        logger.info("    %-10s type=%-12s → %s", route.match, route.type, route.base_url)
    logger.info("  Postgres   : %s", cfg.database_url)
    logger.info("  Dashboard  : http://localhost:%d/dashboard/requests", cfg.proxy_port)
    logger.info("  Set ANTHROPIC_BASE_URL=http://localhost:%d in Claude Code", cfg.proxy_port)
    logger.info("=" * 60)

    return app


if __name__ == "__main__":
    cfg = Config.from_env()
    logging.basicConfig(
        level=cfg.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    app = create_app(cfg)
    app.run(host="0.0.0.0", port=cfg.proxy_port, threaded=True)
