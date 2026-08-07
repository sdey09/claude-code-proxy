FROM node:20-alpine AS frontend-build

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY proxy.py forwarder.py sse_accumulator.py db.py dashboard.py cost.py config.py routing.py openai_compat.py upstreams.yaml ./
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

RUN uv sync --script proxy.py

EXPOSE 8888

CMD ["uv", "run", "proxy.py"]
