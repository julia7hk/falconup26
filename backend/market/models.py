"""Data models for market data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class OHLCV:
    """Single day of price data."""

    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass(frozen=True, slots=True)
class Quote:
    """Current price snapshot for a symbol."""

    symbol: str
    price: float
    change: float
    change_percent: float
    timestamp: datetime
