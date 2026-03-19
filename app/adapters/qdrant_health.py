"""Qdrant readiness checks."""

from __future__ import annotations

from urllib import request

from app.config import Settings


def check_qdrant(settings: Settings) -> tuple[bool, str]:
    url = f"http://{settings.qdrant_host}:{settings.qdrant_port}/collections"
    try:
        req = request.Request(url, method="GET")
        with request.urlopen(req, timeout=settings.qdrant_http_timeout_seconds) as response:
            response.read()
        return True, f"reachable:{url}"
    except Exception as exc:
        return False, str(exc)

