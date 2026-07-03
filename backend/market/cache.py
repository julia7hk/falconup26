"""Redis-backed TTL cache for market data.

Prevents hammering upstream APIs on repeated requests. Keyed by
(method, symbol, args). Entries expire after a configurable TTL.

Requires REDIS_URL env var (defaults to redis://localhost:6379/0).
"""

from __future__ import annotations

import os
import pickle
from typing import Any

import redis


def _get_redis_client() -> redis.Redis:
    url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    return redis.from_url(url)


class TTLCache:
    """Redis-backed cache with per-entry expiry."""

    def __init__(self, default_ttl: int = 300, prefix: str = "falconup"):
        """default_ttl: seconds before an entry expires (default 5 min)."""
        self._r = _get_redis_client()
        self._default_ttl = default_ttl
        self._prefix = prefix

    def _key(self, key: str) -> str:
        return f"{self._prefix}:{key}"

    def get(self, key: str) -> Any | None:
        data = self._r.get(self._key(key))
        if data is None:
            return None
        return pickle.loads(data)

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        seconds = ttl if ttl is not None else self._default_ttl
        self._r.set(self._key(key), pickle.dumps(value), ex=seconds)

    def invalidate(self, key: str) -> None:
        self._r.delete(self._key(key))

    def clear(self) -> None:
        pattern = f"{self._prefix}:*"
        cursor = 0
        while True:
            cursor, keys = self._r.scan(cursor, match=pattern, count=100)
            if keys:
                self._r.delete(*keys)
            if cursor == 0:
                break
