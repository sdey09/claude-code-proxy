# claude-code-local-observability

A local MITM proxy that intercepts Claude Code API calls, captures prompts/responses to Postgres, and
serves a custom Flask dashboard for browsing requests and cost/usage — without touching the corporate
jellyfish observability pipeline.

## Architecture

```
Claude Code
    │  ANTHROPIC_BASE_URL=http://localhost:8888  (set globally in settings.json)
    ▼
claude-mitm-proxy  (Flask, port 8888)
    │
    ├── routes by model (upstreams.yaml) ──▶  Databricks AI Gateway or api.anthropic.com
    ├── dual-write streaming response ──▶  Claude Code (zero latency overhead)
    ├── captures to Postgres (async, background thread pool)
    └── serves /dashboard  ──▶  request log, request detail, cost & usage charts
```

## Quick Start

### 1. Configure `.env` and `upstreams.yaml`

```bash
cp .env.example .env
```

`upstreams.yaml` maps model-name patterns to upstreams — edit it to point at your
Databricks AI Gateway, api.anthropic.com, or both. See [Routing](#routing) below.

### 2. Start Postgres

```bash
cd claude-code-local-observability
make up
```

- Proxy:     http://localhost:8888
- Dashboard: http://localhost:8888/dashboard/requests
- Postgres:  localhost:5432 (claude/claude, db=claude_proxy)

### 3. Start the proxy

```bash
cd claude-code-local-observability
uv run proxy.py
```

The proxy reads its config from `.env` and its routing table from `upstreams.yaml` automatically — no need to pass env vars manually.

Or use the convenience script (starts Postgres + proxy together):

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
  - match: "gpt-*"                    # any model prefixed gpt- (real OpenAI, OpenRouter, vLLM, ...)
    type: openai
    protocol: openai                  # this upstream speaks OpenAI's /v1/chat/completions shape
    base_url: "https://api.openai.com"
    auth_header: "Authorization"
    api_key_env: "OPENAI_API_KEY"

  - match: "*"                        # everything else
    type: anthropic
    protocol: anthropic
    base_url: "https://api.anthropic.com"
```

Omit `auth_header`/`api_key_env` on a route to pass the client's original auth headers through unchanged
(e.g. Claude Code's own `ANTHROPIC_API_KEY`/OAuth token) — that's the right default for a direct Anthropic route.
Add them when a route needs different credentials, like a Databricks personal access token.

`protocol` declares which wire format **the upstream** speaks — `anthropic` (default, backward
compatible with every existing config) or `openai`. It's independent of which entry point the
client used:

| Client hits | Upstream `protocol` | Behavior |
|---|---|---|
| `/v1/messages` | `anthropic` | Passthrough, byte-for-byte (Claude Code's normal path) |
| `/v1/messages` | `openai` | Translate Anthropic request → OpenAI, forward, translate response back |
| `/v1/chat/completions` | `anthropic` | Translate OpenAI request → Anthropic, forward, translate response back |
| `/v1/chat/completions` | `openai` | Passthrough, no translation |

In both directions the proxy also translates the auth header name (`x-api-key` ⇄
`Authorization: Bearer`) whenever it's passing the client's own credentials through unchanged.

One known fidelity gap: when translating a *streaming* Anthropic request onto an openai-protocol
upstream, the initial `message_start` event can't report real `input_tokens` (OpenAI-compatible
APIs only return usage once, at the end of the stream) — it's reported as `0` in the live stream.
The persisted cost/token data in Postgres is unaffected: it's computed by parsing the raw upstream
bytes directly, independent of what's shown to the streaming client.

Each proxied request logs which route it took:

```
── REQUEST  POST /v1/messages  model=claude-sonnet-5  upstream=anthropic(https://api.anthropic.com)  stream=false  body=87b
```

## OpenAI-compatible endpoint

Any OpenAI-SDK client (aider, LibreChat, custom scripts, ...) can talk to the proxy too, at:

```
POST http://localhost:8888/v1/chat/completions
GET  http://localhost:8888/v1/models
```

Requests are routed through the same `upstreams.yaml` rules as Claude Code traffic. If the
matched route's upstream is `protocol: anthropic` (the default), the request is translated
OpenAI → Anthropic (`messages`, `system`, `tools`/`tool_choice`, `stream`, streaming tool-call
deltas, etc.) and the response translated back — including incremental translation of streamed
responses. If the matched route is `protocol: openai`, the request passes straight through with
no translation. Requests/responses are captured and costed exactly like `/v1/messages` traffic,
just tagged with `path=/v1/chat/completions` in the dashboard. See [Routing](#routing) for the
full translation matrix.

Point an OpenAI client at it with `model` set to whatever `upstreams.yaml` matches (e.g.
`claude-sonnet-5`), and `OPENAI_API_KEY`/`Authorization: Bearer <key>` — it's translated to
Anthropic's `x-api-key` header for routes that pass client auth through unchanged.

## What gets captured

Every API call is stored in Postgres (`requests` table):

```bash
psql "$DATABASE_URL" -c \
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
| `response_body` | Full response body/events (JSON) |

## Dashboard

Open http://localhost:8888/dashboard/requests for the custom UI:

| Page | What it shows |
|------|----------------|
| `/dashboard/requests` | Filterable, paginated table of captured requests (model, status, tokens, cost, timing) |
| `/dashboard/requests/<id>` | Full request/response JSON for a single call |
| `/dashboard/costs` | Summary stats, cost-over-time chart, and cost-by-model breakdown |

It's a React app (`frontend/`) built with Vite; `dashboard.py` serves the production build (`frontend/dist`) plus the
JSON API it talks to (`/dashboard/api/...`). `start.sh` and the Dockerfile build it automatically. For active
frontend development with hot reload, run `cd frontend && npm install && npm run dev` (proxies API calls to the
proxy on `:8888`) instead of relying on the static build.

## Configuration

All config via `.env` (or environment variables directly):

| Variable | Default | Description |
|----------|---------|-------------|
| `UPSTREAM_ROUTES_FILE` | `upstreams.yaml` | Path to the routing table |
| `DATABRICKS_TOKEN` | *(unset)* | Used by routes with `api_key_env: DATABRICKS_TOKEN` |
| `PROXY_PORT` | `8888` | Proxy listening port |
| `DATABASE_URL` | `postgresql://claude:claude@localhost:5432/claude_proxy` | Postgres connection string |
| `MAX_BODY_STORE_BYTES` | `524288` | Max request/response body size to store |
| `PROXY_SSL_VERIFY` | `true` | Set to `false` to skip TLS verification |
| `LOG_LEVEL` | `INFO` | Python log level |

## File Structure

```
claude-code-local-observability/
├── proxy.py                  # Flask app: request handler + proxy entry point
├── dashboard.py              # Flask blueprint: dashboard JSON API + SPA serving
├── openai_compat.py          # OpenAI Chat Completions ⇄ Anthropic Messages translation
├── forwarder.py              # Upstream HTTP client (requests), header handling
├── sse_accumulator.py        # SSE stream parser
├── db.py                     # Postgres schema + queries (psycopg2)
├── cost.py                   # Token → USD cost table
├── config.py                 # Environment variable config
├── routing.py                # Model → upstream routing table
├── upstreams.yaml            # Routing rules (Databricks, Anthropic, ...)
├── frontend/                 # React dashboard (Vite) — builds to frontend/dist, served by dashboard.py
├── start.sh                  # Convenience script: builds frontend, starts Postgres + proxy
├── .env                      # Local config (gitignored)
├── .env.example              # Template
├── docker-compose.yml        # Postgres + proxy
└── data/                     # Legacy SQLite DB from a prior version (unused, gitignored)
```
