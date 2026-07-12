from __future__ import annotations

import logging
from typing import Optional

from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.metrics import Counter, Histogram, UpDownCounter

logger = logging.getLogger(__name__)

_provider: Optional[MeterProvider] = None
_requests_total: Optional[Counter] = None
_request_duration: Optional[Histogram] = None
_input_tokens: Optional[Counter] = None
_output_tokens: Optional[Counter] = None
_cost_usd: Optional[Counter] = None
_db_rows: Optional[UpDownCounter] = None
_db_rows_current: int = 0


def init_metrics(otel_endpoint: str, export_interval_ms: int) -> None:
    global _provider, _requests_total, _request_duration
    global _input_tokens, _output_tokens, _cost_usd, _db_rows

    resource = Resource.create({
        "service.name": "claude-mitm-proxy",
        "service.version": "0.1.0",
    })
    exporter = OTLPMetricExporter(
        endpoint=f"{otel_endpoint.rstrip('/')}/v1/metrics",
        timeout=5,
    )
    reader = PeriodicExportingMetricReader(exporter, export_interval_millis=export_interval_ms)
    _provider = MeterProvider(resource=resource, metric_readers=[reader])

    meter = _provider.get_meter("claude-mitm-proxy", version="0.1.0")

    _requests_total = meter.create_counter(
        name="proxy_request_total",
        description="Total API requests intercepted by the proxy",
        unit="1",
    )
    _request_duration = meter.create_histogram(
        name="proxy_request_duration",
        description="End-to-end latency of intercepted requests (seconds)",
        unit="s",
    )
    _input_tokens = meter.create_counter(
        name="proxy_input_tokens_total",
        description="Input tokens seen by the proxy",
        unit="1",
    )
    _output_tokens = meter.create_counter(
        name="proxy_output_tokens_total",
        description="Output tokens seen by the proxy",
        unit="1",
    )
    _cost_usd = meter.create_counter(
        name="proxy_cost_usd_total",
        description="Estimated cost of intercepted requests (USD)",
        unit="USD",
    )
    _db_rows = meter.create_up_down_counter(
        name="proxy_db_rows",
        description="Total rows in the proxy SQLite database",
        unit="1",
    )

    logger.info("OTLP metrics initialised → %s (interval %dms)", otel_endpoint, export_interval_ms)


def shutdown_metrics() -> None:
    if _provider:
        _provider.shutdown()


def emit(
    model: str,
    status_code: int,
    total_s: float,
    input_tokens: int,
    output_tokens: int,
    cache_write_tokens: int,
    cache_read_tokens: int,
    cost_usd: float,
) -> None:
    global _db_rows_current
    if _requests_total is None:
        return

    model_attr = {"model": model}
    _requests_total.add(1, {**model_attr, "status_code": str(status_code)})
    _request_duration.record(total_s, model_attr)
    _input_tokens.add(input_tokens, {**model_attr, "cache_type": "normal"})
    _input_tokens.add(cache_write_tokens, {**model_attr, "cache_type": "cache_write"})
    _input_tokens.add(cache_read_tokens, {**model_attr, "cache_type": "cache_read"})
    _output_tokens.add(output_tokens, model_attr)
    _cost_usd.add(cost_usd, model_attr)
    _db_rows.add(1)
