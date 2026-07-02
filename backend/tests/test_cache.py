"""Tests for the TTL cache."""

import time
from unittest.mock import patch

from market.cache import TTLCache


def test_set_and_get():
    cache = TTLCache(default_ttl=60)
    cache.set("k", "v")
    assert cache.get("k") == "v"


def test_miss_returns_none():
    cache = TTLCache()
    assert cache.get("nonexistent") is None


def test_expired_entry_returns_none():
    cache = TTLCache(default_ttl=1)
    cache.set("k", "v", ttl=0)
    # monotonic clock has advanced past the 0-second TTL
    assert cache.get("k") is None


def test_custom_ttl_overrides_default():
    cache = TTLCache(default_ttl=0)
    cache.set("k", "v", ttl=9999)
    assert cache.get("k") == "v"


def test_invalidate():
    cache = TTLCache()
    cache.set("k", "v")
    cache.invalidate("k")
    assert cache.get("k") is None


def test_invalidate_missing_key_is_noop():
    cache = TTLCache()
    cache.invalidate("nope")  # should not raise


def test_clear():
    cache = TTLCache()
    cache.set("a", 1)
    cache.set("b", 2)
    cache.clear()
    assert cache.get("a") is None
    assert cache.get("b") is None
