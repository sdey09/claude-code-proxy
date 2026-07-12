from __future__ import annotations

import logging
from typing import Optional

import aiohttp
from aiohttp import web

from config import Config
from routing import Route, apply_route_auth

logger = logging.getLogger(__name__)

# Hop-by-hop headers that must never be forwarded
_HOP_BY_HOP = frozenset({
    "host",
    "content-length",
    "transfer-encoding",
    "accept-encoding",
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "upgrade",
})


def _filter_request_headers(headers: "web.CIMultiDictProxy[str]") -> dict[str, str]:
    return {k: v for k, v in headers.items() if k.lower() not in _HOP_BY_HOP}


def _filter_response_headers(headers: "aiohttp.CIMultiDictProxy[str]") -> dict[str, str]:
    return {k: v for k, v in headers.items() if k.lower() not in _HOP_BY_HOP}


class Forwarder:
    def __init__(self, cfg: Config) -> None:
        self._ssl = cfg.make_ssl_context()
        self._session: Optional[aiohttp.ClientSession] = None

    async def start(self) -> None:
        connector = aiohttp.TCPConnector(ssl=self._ssl)
        self._session = aiohttp.ClientSession(
            connector=connector,
            auto_decompress=False,  # pass compressed bytes through as-is
        )

    async def close(self) -> None:
        if self._session:
            await self._session.close()

    async def forward(
        self,
        request: web.Request,
        body: bytes,
        route: Route,
    ) -> aiohttp.ClientResponse:
        upstream_url = route.base_url.rstrip("/") + str(request.rel_url)
        headers = _filter_request_headers(request.headers)
        headers["content-length"] = str(len(body))
        apply_route_auth(route, headers)

        logger.debug("→ upstream[%s] %s %s (%d bytes)", route.type, request.method, upstream_url, len(body))

        resp = await self._session.request(
            method=request.method,
            url=upstream_url,
            headers=headers,
            data=body,
            allow_redirects=False,
        )
        return resp

    @staticmethod
    def response_headers(upstream: aiohttp.ClientResponse) -> dict[str, str]:
        return _filter_response_headers(upstream.headers)
