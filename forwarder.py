from __future__ import annotations

import logging

import requests

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


def filter_headers(headers) -> dict[str, str]:
    return {k: v for k, v in headers.items() if k.lower() not in _HOP_BY_HOP}


class Forwarder:
    def __init__(self, cfg: Config) -> None:
        self.verify = cfg.ssl_verify
        self.session = requests.Session()

    def close(self) -> None:
        self.session.close()

    def forward(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes,
        route: Route,
    ) -> requests.Response:
        apply_route_auth(route, headers)

        logger.debug("→ upstream[%s] %s %s (%d bytes)", route.type, method, url, len(body))

        return self.session.request(
            method=method,
            url=url,
            headers=headers,
            data=body,
            stream=True,
            verify=self.verify,
            allow_redirects=False,
        )

    @staticmethod
    def response_headers(upstream: requests.Response) -> dict[str, str]:
        return filter_headers(upstream.headers)
