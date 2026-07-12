# claude-code-local-observability

A local MITM proxy that intercepts Claude Code API calls, captures prompts/responses to SQLite, and emits metrics into a local Grafana stack — without touching the corporate jellyfish observability pipeline.

## Architecture

```
Claude Code
    │  ANTHROPIC_BASE_URL=http://localhost:8888  (set globally in settings.json)
    ▼
claude-mitm-proxy  (aiohttp, port 8888)
    │
    ├── routes by model (upstreams.yaml) ──▶  Databricks AI Gateway or api.anthropic.com
    ├── dual-write SSE stream ──▶  Claude Code (zero latency overhead)
    ├── captures to SQLite  (data/claude-proxy.db)
    └── emits OTLP metrics ──▶  OTel Collector :4318
                                    └──▶  Prometheus :9090
                                              └──▶  Grafana :3000
```

## Quick Start

### 1. Configure `.env` and `upstreams.yaml`

```bash
cp .env.example .env
```

`upstreams.yaml` maps model-name patterns to upstreams — edit it to point at your
Databricks AI Gateway, api.anthropic.com, or both. See [Routing](#routing) below.

### 2. Start the observability stack

```bash
cd ~/Documents/dx/dev-scripts/claude-code-local-observability
make up
```

- Grafana:    http://localhost:3000  (admin/admin)
- Prometheus: http://localhost:9090
- OTel:       http://localhost:4318

### 3. Start the proxy

```bash
cd ~/Documents/dx/dev-scripts/claude-code-local-observability
uv run proxy.py
```

The proxy reads its config from `.env` and its routing table from `upstreams.yaml` automatically — no need to pass env vars manually.

Or use the convenience script (starts stack + proxy together):

```bash
./start.sh
```

### 4. Point Claude Code at the proxy

`ANTHROPIC_BASE_URL` is set globally in `~/.claude/settings.json`:

```json
"env": {
  "ANTHROPIC_BASE_URL": "http://localhost:8888"
}
```

**Important:** The proxy must be running before starting any Claude Code session, otherwise API calls will fail to connect.

Verify the active URL in any Claude Code session with `/status` — look for `Anthropic base URL: http://localhost:8888`.

## Reverting

To bypass the proxy, remove (or comment out) `ANTHROPIC_BASE_URL` in `~/.claude/settings.json` — Claude Code
falls back to talking to Anthropic (or your Databricks gateway, if that's configured elsewhere) directly.

## Routing

`upstreams.yaml` controls where each request goes, based on the request's `model` field. Rules are
evaluated top to bottom; the first pattern match wins:

```yaml
routes:
  - match: "ias-*"                    # any model prefixed ias- (corporate/internal)
    type: databricks
    base_url: "https://your-gateway.com/ai-gateway/anthropic"
    auth_header: "Authorization"      # optional: override this header on the outgoing request
    api_key_env: "DATABRICKS_TOKEN"   # optional: value comes from this env var (sent as "Bearer <value>")

  - match: "*"                        # everything else
    type: anthropic
    base_url: "https://api.anthropic.com"
```

Omit `auth_header`/`api_key_env` on a route to pass the client's original auth headers through unchanged
(e.g. Claude Code's own `ANTHROPIC_API_KEY`/OAuth token) — that's the right default for a direct Anthropic route.
Add them when a route needs different credentials, like a Databricks personal access token.

Each proxied request logs which route it took:

```
── REQUEST  POST /v1/messages  model=claude-sonnet-5  upstream=anthropic(https://api.anthropic.com)  stream=false  body=87b
```

## What gets captured

Every API call is stored in `data/claude-proxy.db`:

```bash
sqlite3 data/claude-proxy.db \
  "SELECT timestamp_utc, model, input_tokens, output_tokens, cost_usd, stop_reason
   FROM requests ORDER BY id DESC LIMIT 10;"
```

| Column | Description |
|--------|-------------|
| `request_id` | Anthropic message ID |
| `model` | Model used (from response) |
| `input_tokens` | Input token count (incl. cache) |
| `output_tokens` | Output token count |
| `cache_write_tokens` | Prompt cache write tokens |
| `cache_read_tokens` | Prompt cache read tokens |
| `cost_usd` | Estimated cost in USD |
| `stop_reason` | `end_turn`, `max_tokens`, etc. |
| `ttfb_s` | Time to first byte (seconds) |
| `total_s` | Total request duration (seconds) |
| `request_body` | Full prompt payload (JSON) |
| `response_body` | Full response SSE events (JSON) |

## Metrics in Grafana

The proxy emits these metrics to Prometheus (all prefixed `claude_proxy_*`):

| Metric | Type | Labels |
|--------|------|--------|
| `claude_proxy_request_total` | counter | `model`, `status_code` |
| `claude_proxy_request_duration` | histogram | `model` |
| `claude_proxy_input_tokens_total` | counter | `model`, `cache_type` |
| `claude_proxy_output_tokens_total` | counter | `model` |
| `claude_proxy_cost_usd_total` | counter | `model` |

Open Grafana at http://localhost:3000 → Dashboards → **Claude Proxy — Request Inspector**.

## Configuration

All config via `.env` (or environment variables directly):

| Variable | Default | Description |
|----------|---------|-------------|
| `UPSTREAM_ROUTES_FILE` | `upstreams.yaml` | Path to the routing table |
| `DATABRICKS_TOKEN` | *(unset)* | Used by routes with `api_key_env: DATABRICKS_TOKEN` |
| `PROXY_PORT` | `8888` | Proxy listening port |
| `DB_PATH` | `./data/claude-proxy.db` | SQLite database path |
| `OTEL_ENDPOINT` | `http://localhost:4318` | OTel collector HTTP endpoint |
| `OTEL_EXPORT_INTERVAL_MS` | `30000` | Metrics export interval |
| `MAX_BODY_STORE_BYTES` | `524288` | Max request/response body size to store |
| `PROXY_SSL_VERIFY` | `true` | Set to `false` to skip TLS verification |
| `LOG_LEVEL` | `INFO` | Python log level |

## File Structure

```
claude-code-local-observability/
├── proxy.py                  # Main aiohttp app + request handler
├── forwarder.py              # Upstream HTTP client, header handling
├── sse_accumulator.py        # SSE stream parser
├── db.py                     # SQLite schema + async writes
├── metrics.py                # OTLP metrics emission
├── cost.py                   # Token → USD cost table
├── config.py                 # Environment variable config
├── routing.py                # Model → upstream routing table
├── upstreams.yaml            # Routing rules (Databricks, Anthropic, ...)
├── start.sh                  # Convenience script: starts stack + proxy
├── .env                      # Local config (gitignored)
├── .env.example              # Template
├── docker-compose.yml        # Grafana + Prometheus + Loki + OTel stack
├── otel-collector-config.yaml
├── prometheus.yml
├── data/                     # SQLite DB (gitignored)
└── grafana/
    ├── dashboards/
    └── provisioning/
```
