from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class Route:
    match: str
    type: str
    base_url: str
    path: Optional[str] = None
    auth_header: Optional[str] = None
    api_key_env: Optional[str] = None


def load_routes(path: str) -> list[Route]:
    routes_file = Path(path)
    if not routes_file.exists():
        raise RuntimeError(f"upstream routes file not found: {path}")
    data = yaml.safe_load(routes_file.read_text()) or {}
    raw_routes = data.get("routes") or []
    if not raw_routes:
        raise RuntimeError(f"{path} defines no routes")
    return [Route(**r) for r in raw_routes]


def resolve_route(routes: list[Route], model: str) -> Route:
    for route in routes:
        if fnmatch.fnmatch(model or "", route.match):
            return route
    raise RuntimeError(f"no upstream route matches model {model!r}")


def apply_route_auth(route: Route, headers: dict[str, str]) -> None:
    if not route.auth_header or not route.api_key_env:
        return
    token = os.environ.get(route.api_key_env)
    if not token:
        raise RuntimeError(f"{route.api_key_env} env var is required for route type {route.type!r}")
    headers[route.auth_header] = f"Bearer {token}"
