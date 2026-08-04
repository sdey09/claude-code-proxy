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
from cost import estimate_cost
from dashboard import dashboard_bp
from db import RequestRecord
from forwarder import Forwarder, filter_headers
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
