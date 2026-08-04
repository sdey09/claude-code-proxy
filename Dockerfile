FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY proxy.py forwarder.py sse_accumulator.py db.py dashboard.py cost.py config.py routing.py upstreams.yaml ./
COPY templates ./templates
COPY static ./static

RUN uv sync --script proxy.py

EXPOSE 8888

CMD ["uv", "run", "proxy.py"]
