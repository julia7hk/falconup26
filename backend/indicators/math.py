"""Pure indicator computation functions.

Every function takes plain lists of floats (prices) and returns a result
dataclass.  No database, no network, no side effects.
"""

from __future__ import annotations

import numpy as np

from indicators.models import (
    ATRResult,
    BetaResult,
    BollingerResult,
    MACDResult,
    RSIResult,
    SMACrossoverResult,
    SharpeResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ema(data: list[float], period: int) -> list[float]:
    """Exponential moving average.

    Uses the standard multiplier: 2 / (period + 1).
    First value is the SMA of the first `period` points.
    """
    if len(data) < period:
        return []
    multiplier = 2 / (period + 1)
    result = [sum(data[:period]) / period]
    for price in data[period:]:
        result.append((price - result[-1]) * multiplier + result[-1])
    return result


def _sma(data: list[float], period: int) -> list[float]:
    """Simple moving average."""
    if len(data) < period:
        return []
    result = []
    window_sum = sum(data[:period])
    result.append(window_sum / period)
    for i in range(period, len(data)):
        window_sum += data[i] - data[i - period]
        result.append(window_sum / period)
    return result


# ---------------------------------------------------------------------------
# Indicators
# ---------------------------------------------------------------------------


def rsi(closes: list[float], period: int = 14) -> RSIResult:
    """Relative Strength Index using Wilder's smoothing.

    Needs at least ``period + 1`` close prices.
    """
    if len(closes) < period + 1:
        raise ValueError(f"RSI needs at least {period + 1} closes, got {len(closes)}")

    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0.0 for d in deltas]
    losses = [-d if d < 0 else 0.0 for d in deltas]

    # Wilder's smoothing: first value is SMA, then exponential
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        value = 100.0
    else:
        rs = avg_gain / avg_loss
        value = 100 - (100 / (1 + rs))

    if value < 30:
        signal = "oversold"
    elif value > 70:
        signal = "overbought"
    else:
        signal = "neutral"

    return RSIResult(value=round(value, 2), signal=signal)


def macd(
    closes: list[float],
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9,
) -> MACDResult:
    """MACD — Moving Average Convergence Divergence.

    Needs at least ``slow + signal_period`` close prices.
    """
    min_len = slow + signal_period
    if len(closes) < min_len:
        raise ValueError(f"MACD needs at least {min_len} closes, got {len(closes)}")

    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)

    # Align: ema_fast starts at index `fast`, ema_slow at index `slow`.
    # Trim ema_fast so both lists end at the same point.
    offset = slow - fast
    ema_fast_aligned = ema_fast[offset:]

    macd_line_values = [f - s for f, s in zip(ema_fast_aligned, ema_slow)]
    signal_line_values = _ema(macd_line_values, signal_period)

    # Align macd_line to signal_line
    macd_trimmed = macd_line_values[signal_period - 1 :]

    current_macd = macd_trimmed[-1]
    current_signal = signal_line_values[-1]
    current_histogram = current_macd - current_signal

    if current_histogram > 0 and current_macd > current_signal:
        signal = "bullish"
    elif current_histogram < 0 and current_macd < current_signal:
        signal = "bearish"
    else:
        signal = "neutral"

    return MACDResult(
        macd_line=round(current_macd, 4),
        signal_line=round(current_signal, 4),
        histogram=round(current_histogram, 4),
        signal=signal,
    )


def bollinger_width(
    closes: list[float],
    period: int = 20,
    num_std: float = 2.0,
) -> BollingerResult:
    """Bollinger Band width (normalized).

    Width = (upper - lower) / middle.
    """
    if len(closes) < period:
        raise ValueError(
            f"Bollinger needs at least {period} closes, got {len(closes)}"
        )

    # Use the most recent `period` closes for the current bands
    window = closes[-period:]
    middle = sum(window) / period
    std = (sum((x - middle) ** 2 for x in window) / period) ** 0.5

    upper = middle + num_std * std
    lower = middle - num_std * std
    width = (upper - lower) / middle if middle != 0 else 0.0

    # Compare current width to average width over available history
    sma_values = _sma(closes, period)
    if len(sma_values) >= 2:
        widths = []
        for i in range(len(sma_values)):
            start = i
            end = i + period
            w = closes[start:end]
            m = sma_values[i]
            s = (sum((x - m) ** 2 for x in w) / period) ** 0.5
            widths.append((2 * num_std * s) / m if m != 0 else 0.0)
        avg_width = sum(widths) / len(widths)
        if width > avg_width * 1.2:
            signal = "high_volatility"
        elif width < avg_width * 0.8:
            signal = "low_volatility"
        else:
            signal = "neutral"
    else:
        signal = "neutral"

    return BollingerResult(
        width=round(width, 4),
        upper=round(upper, 2),
        lower=round(lower, 2),
        signal=signal,
    )


def sma_crossover(closes: list[float]) -> SMACrossoverResult:
    """50/200-day SMA crossover detection.

    Returns the most recent crossover type and how many trading days ago
    it occurred.
    """
    if len(closes) < 200:
        raise ValueError(
            f"SMA crossover needs at least 200 closes, got {len(closes)}"
        )

    sma_50_values = _sma(closes, 50)
    sma_200_values = _sma(closes, 200)

    # sma_50 starts at index 50, sma_200 starts at index 200.
    # Align them: trim sma_50 so both cover the same date range.
    offset = 200 - 50
    sma_50_aligned = sma_50_values[offset:]

    current_sma_50 = sma_50_aligned[-1]
    current_sma_200 = sma_200_values[-1]

    # Scan backwards for the most recent crossover
    crossover_type = "none"
    days_since_cross = None

    for i in range(len(sma_50_aligned) - 1, 0, -1):
        prev_diff = sma_50_aligned[i - 1] - sma_200_values[i - 1]
        curr_diff = sma_50_aligned[i] - sma_200_values[i]

        if prev_diff <= 0 < curr_diff:
            crossover_type = "golden_cross"
            days_since_cross = len(sma_50_aligned) - 1 - i
            break
        elif prev_diff >= 0 > curr_diff:
            crossover_type = "death_cross"
            days_since_cross = len(sma_50_aligned) - 1 - i
            break

    return SMACrossoverResult(
        sma_50=round(current_sma_50, 2),
        sma_200=round(current_sma_200, 2),
        crossover_type=crossover_type,
        days_since_cross=days_since_cross,
    )


def atr(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period: int = 14,
) -> ATRResult:
    """Average True Range.

    True Range = max(high-low, |high-prev_close|, |low-prev_close|).
    ATR = Wilder's smoothing of True Range over ``period`` days.
    """
    if len(closes) < period + 1:
        raise ValueError(
            f"ATR needs at least {period + 1} data points, got {len(closes)}"
        )
    if not (len(highs) == len(lows) == len(closes)):
        raise ValueError("highs, lows, and closes must be the same length")

    true_ranges = []
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        true_ranges.append(tr)

    # Wilder's smoothing (same as RSI)
    atr_value = sum(true_ranges[:period]) / period
    for i in range(period, len(true_ranges)):
        atr_value = (atr_value * (period - 1) + true_ranges[i]) / period

    current_close = closes[-1]
    atr_pct = (atr_value / current_close * 100) if current_close != 0 else 0.0

    return ATRResult(
        value=round(atr_value, 4),
        atr_percent=round(atr_pct, 2),
    )


def beta(
    symbol_closes: list[float],
    benchmark_closes: list[float],
) -> BetaResult:
    """Beta vs benchmark (typically S&P 500 / SPY).

    Both close arrays must be the same length and pre-aligned by date.
    Uses daily returns over the full period.
    """
    if len(symbol_closes) != len(benchmark_closes):
        raise ValueError(
            f"Arrays must be same length: symbol={len(symbol_closes)}, "
            f"benchmark={len(benchmark_closes)}"
        )
    if len(symbol_closes) < 2:
        raise ValueError("Need at least 2 data points for beta")

    sym = np.array(symbol_closes)
    bench = np.array(benchmark_closes)

    sym_returns = np.diff(sym) / sym[:-1]
    bench_returns = np.diff(bench) / bench[:-1]

    cov_matrix = np.cov(sym_returns, bench_returns)
    covariance = cov_matrix[0, 1]
    bench_variance = cov_matrix[1, 1]

    if bench_variance == 0:
        beta_value = 0.0
    else:
        beta_value = covariance / bench_variance

    if beta_value < 0.8:
        interpretation = "less volatile than market"
    elif beta_value <= 1.2:
        interpretation = "moves with market"
    elif beta_value <= 1.5:
        interpretation = "more volatile than market"
    else:
        interpretation = "significantly more volatile than market"

    return BetaResult(
        value=round(float(beta_value), 2),
        interpretation=interpretation,
    )


def sharpe_ratio(
    closes: list[float],
    risk_free_annual: float,
    trading_days: int = 252,
) -> SharpeResult:
    """Annualized Sharpe ratio.

    ``risk_free_annual`` should be a percentage (e.g. 5.33 for 5.33%).
    """
    if len(closes) < 2:
        raise ValueError("Need at least 2 data points for Sharpe ratio")

    prices = np.array(closes)
    daily_returns = np.diff(prices) / prices[:-1]

    daily_rf = (risk_free_annual / 100) / trading_days
    excess_returns = daily_returns - daily_rf

    std = np.std(excess_returns, ddof=1)
    if std == 0:
        sharpe = 0.0
    else:
        sharpe = (np.mean(excess_returns) / std) * np.sqrt(trading_days)

    sharpe = float(sharpe)

    if sharpe >= 2.0:
        interpretation = "excellent risk-adjusted return"
    elif sharpe >= 1.0:
        interpretation = "good risk-adjusted return"
    elif sharpe >= 0:
        interpretation = "positive but below-average risk-adjusted return"
    else:
        interpretation = "negative risk-adjusted return"

    return SharpeResult(
        value=round(sharpe, 2),
        risk_free_rate=risk_free_annual,
        interpretation=interpretation,
    )
