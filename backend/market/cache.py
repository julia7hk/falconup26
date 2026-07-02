"""In-memory TTL cache for market data.

Prevents hammering the upstream API on repeated requests. Keyed by
(method, symbol, args). Entries expire after a configurable TTL.
"""

from __future__ import annotations

import time
from typing import Any


class TTLCache:
    """Simple dict-based cache with per-entry expiry."""

    def __init__(self, default_ttl: int = 300):
        """default_ttl: seconds before an entry expires (default 5 min)."""
        self._store: dict[str, tuple[float, Any]] = {}
        self._default_ttl = default_ttl

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        expires_at = time.monotonic() + (ttl if ttl is not None else self._default_ttl)
        self._store[key] = (expires_at, value)

    def invalidate(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()
