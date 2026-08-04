from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv(path: str = ".env") -> None:
    env_file = Path(path)
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass
class Config:
    upstream_routes_file: str
    proxy_port: int
    database_url: str
    max_body_store_bytes: int
    ssl_verify: bool
    log_level: str

    @classmethod
    def from_env(cls) -> Config:
        _load_dotenv()
        return cls(
            upstream_routes_file=os.environ.get("UPSTREAM_ROUTES_FILE", "upstreams.yaml"),
            proxy_port=int(os.environ.get("PROXY_PORT", "8888")),
            database_url=os.environ.get(
                "DATABASE_URL", "postgresql://claude:claude@localhost:5432/claude_proxy"
            ),
            max_body_store_bytes=int(os.environ.get("MAX_BODY_STORE_BYTES", str(512 * 1024))),
            ssl_verify=os.environ.get("PROXY_SSL_VERIFY", "true").lower() not in ("false", "0", "no"),
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
        )
