"""Shared test fixtures — patches Redis with fakeredis so tests need no running server."""

from unittest.mock import patch

import fakeredis
import pytest


@pytest.fixture(autouse=True)
def _fake_redis():
    """Replace all Redis connections with fakeredis for every test."""
    with patch("market.cache._get_redis_client", return_value=fakeredis.FakeRedis()):
        yield
