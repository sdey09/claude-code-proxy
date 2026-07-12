# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "aiohttp>=3.9",
#   "aiosqlite>=0.20",
#   "opentelemetry-sdk>=1.24",
#   "opentelemetry-exporter-otlp-proto-http>=1.24",
#   "pyyaml>=6.0",
# ]
# ///
from __future__ import annotations

import asyncio
import gzip
import json
import logging
import time
import zlib
from datetime import datetime, timezone
from typing import Optional

from aiohttp import web

from config import Config
from cost import estimate_cost
from db import RequestRecord, init_db, insert_record
from forwarder import Forwarder
from metrics import emit, init_metrics, shutdown_metrics
from routing import Route, load_routes, resolve_route
from sse_accumulator import ParsedResponse, parse_json_response, parse_sse_buffer

logger = logging.getLogger(__name__)


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


async def _handle(request: web.Request) -> web.StreamResponse:
    cfg: Config = request.app["cfg"]
    fwd: Forwarder = request.app["forwarder"]
    db = request.app["db"]

    timestamp_utc = datetime.now(timezone.utc).isoformat()
    body = await request.read()

    # Parse request body for logging/storage
    request_json: Optional[dict] = None
    try:
        request_json = json.loads(body) if body else None
    except json.JSONDecodeError:
        pass

    is_stream = bool(request_json and request_json.get("stream", False))
    path = str(request.rel_url)
    model_hint = (request_json or {}).get("model", "?")

    try:
        route = resolve_route(request.app["routes"], model_hint)
    except RuntimeError as exc:
        logger.error("✗ ROUTING FAILED: %s", exc)
        raise web.HTTPBadGateway(reason=str(exc))

    logger.info("── REQUEST  %s %s  model=%s  upstream=%s(%s)  stream=%s  body=%db",
                request.method, path, model_hint, route.type, route.base_url, is_stream, len(body))

    t_start = time.monotonic()
    ttfb_s: Optional[float] = None

    try:
        upstream = await fwd.forward(request, body, route)
    except RuntimeError as exc:
        logger.error("✗ ROUTING FAILED: %s", exc)
        raise web.HTTPBadGateway(reason=str(exc))
    except Exception as exc:
        logger.error("✗ UPSTREAM CONNECT FAILED: %s", exc)
        raise web.HTTPBadGateway(reason=str(exc))

    status = upstream.status
    resp_headers = Forwarder.response_headers(upstream)

    # Determine if the upstream returned a streaming response
    content_type = upstream.headers.get("content-type", "")
    content_encoding = upstream.headers.get("content-encoding", "")
    is_sse_response = "text/event-stream" in content_type

    logger.info("── UPSTREAM  status=%d  content-type=%s", status, content_type)

    if status >= 400:
        logger.warning("✗ UPSTREAM ERROR  status=%d  path=%s", status, path)

    downstream = web.StreamResponse(status=status, headers=resp_headers)
    await downstream.prepare(request)

    raw_buffer: list[bytes] = []
    error_body: Optional[str] = None
    chunk_count = 0

    if is_sse_response:
        # Dual-write: forward each chunk immediately, buffer in parallel
        async for chunk in upstream.content.iter_chunked(8192):
            if ttfb_s is None:
                ttfb_s = time.monotonic() - t_start
                logger.info("── FIRST BYTE  ttfb=%.3fs", ttfb_s)
            await downstream.write(chunk)
            raw_buffer.append(chunk)
            chunk_count += 1
        logger.debug("── SSE DONE  chunks=%d  bytes=%d", chunk_count, sum(len(c) for c in raw_buffer))
    else:
        # Non-streaming (JSON or error)
        raw_response = await upstream.read()
        ttfb_s = time.monotonic() - t_start
        raw_buffer.append(raw_response)
        await downstream.write(raw_response)
        if status >= 400:
            error_body = _decompress(raw_response, content_encoding).decode(errors="replace")
            logger.error("✗ ERROR BODY: %s", error_body[:500])

    total_s = time.monotonic() - t_start
    await downstream.write_eof()

    # Parse accumulated data and persist (non-blocking)
    asyncio.create_task(
        _persist(
            cfg=cfg,
            db=db,
            timestamp_utc=timestamp_utc,
            path=path,
            is_stream=is_stream,
            is_sse_response=is_sse_response,
            request_body=body,
            request_json=request_json,
            raw_buffer=raw_buffer,
            content_encoding=content_encoding,
            status=status,
            ttfb_s=ttfb_s,
            total_s=total_s,
            error_body=error_body,
        )
    )

    return downstream


async def _persist(
    cfg: Config,
    db,
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

    # Use model from request body as fallback if SSE parse didn't find it
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

    await insert_record(db, rec, cfg.max_body_store_bytes)

    if status < 400:
        emit(
            model=model or "unknown",
            status_code=status,
            total_s=total_s,
            input_tokens=parsed.input_tokens,
            output_tokens=parsed.output_tokens,
            cache_write_tokens=parsed.cache_write_tokens,
            cache_read_tokens=parsed.cache_read_tokens,
            cost_usd=cost,
        )

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


async def _on_startup(app: web.Application) -> None:
    cfg: Config = app["cfg"]
    logging.basicConfig(
        level=cfg.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    fwd = Forwarder(cfg)
    await fwd.start()
    app["forwarder"] = fwd

    routes: list[Route] = load_routes(cfg.upstream_routes_file)
    app["routes"] = routes

    db = await init_db(cfg.db_path)
    app["db"] = db

    init_metrics(cfg.otel_endpoint, cfg.otel_export_interval_ms)

    logger.info("=" * 60)
    logger.info("  claude-mitm-proxy  READY")
    logger.info("  Listening  : http://0.0.0.0:%d", cfg.proxy_port)
    logger.info("  Routes     : %s", cfg.upstream_routes_file)
    for route in routes:
        logger.info("    %-10s type=%-12s → %s", route.match, route.type, route.base_url)
    logger.info("  SQLite DB  : %s", cfg.db_path)
    logger.info("  OTLP       : %s", cfg.otel_endpoint)
    logger.info("  Set ANTHROPIC_BASE_URL=http://localhost:%d in Claude Code", cfg.proxy_port)
    logger.info("=" * 60)


async def _on_shutdown(app: web.Application) -> None:
    fwd: Forwarder = app.get("forwarder")
    if fwd:
        await fwd.close()
    db = app.get("db")
    if db:
        await db.close()
    shutdown_metrics()


def make_app(cfg: Config) -> web.Application:
    app = web.Application(client_max_size=100 * 1024 * 1024)
    app["cfg"] = cfg
    app.on_startup.append(_on_startup)
    app.on_shutdown.append(_on_shutdown)
    app.router.add_route("*", "/{path_info:.*}", _handle)
    return app


if __name__ == "__main__":
    cfg = Config.from_env()
    app = make_app(cfg)
    web.run_app(app, host="0.0.0.0", port=cfg.proxy_port)
