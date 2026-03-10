"""Shared HTTP client with TTL response cache."""

import os
import time

import httpx

_cache: dict[str, tuple[float, str]] = {}

_timeout = int(os.getenv("REFLEX_DOCS_HTTP_TIMEOUT", "10"))
_client = httpx.Client(timeout=_timeout, follow_redirects=True)


def fetch(url: str, ttl: int = 3600) -> str | None:
    """Fetch a URL with in-process TTL caching.

    Args:
        url: The URL to fetch.
        ttl: Time-to-live for cached responses in seconds (default: 3600).

    Returns:
        Response text, or None on failure.
    """
    now = time.time()
    if url in _cache and now - _cache[url][0] < ttl:
        return _cache[url][1]
    if os.getenv("REFLEX_DOCS_ENABLE_LIVE_FETCH", "true").lower() in ("false", "0", "no"):
        return None
    try:
        r = _client.get(url)
        r.raise_for_status()
        _cache[url] = (now, r.text)
        return r.text
    except Exception:
        return None
