#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load .env
export $(grep -v '^#' .env | xargs)

echo "Starting Postgres..."
docker compose up -d postgres

if [ ! -d frontend/dist ]; then
  echo "Building dashboard frontend..."
  (cd frontend && npm install && npm run build)
fi

echo "Starting proxy on :${PROXY_PORT:-8888}..."
uv run proxy.py &
PROXY_PID=$!

echo ""
echo "Proxy running (PID $PROXY_PID)"
echo "Dashboard: http://localhost:${PROXY_PORT:-8888}/dashboard/requests"
echo "Now launch Claude Code with:"
echo ""
echo "  ANTHROPIC_BASE_URL=http://localhost:${PROXY_PORT:-8888} claude"
echo ""
echo "Press Ctrl+C to stop the proxy."

wait $PROXY_PID
