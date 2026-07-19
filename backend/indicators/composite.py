"""Composite scoring — combine 9 indicators into Buy/Hold/Sell signal."""

from __future__ import annotations

from indicators.models import (
    ATRResult,
    BetaResult,
    BollingerResult,
    CompositeResult,
    MACDResult,
    MaxDrawdownResult,
    RSIResult,
    SMACrossoverResult,
    SharpeResult,
    SortinoResult,
)

# Weights must sum to 1.0.
# Sharpe and Sortino are both risk-adjusted-return measures, so their combined
# weight (0.24) is deliberately close to Sharpe's old solo weight (0.20) — we
# split the budget between them rather than double-counting the same signal.
#
# DELIBERATE STANCE: the volatility/stability cluster — ATR (0.08),
# Bollinger (0.08), beta (0.13), and max_drawdown (0.08), ~0.37 of the score —
# treats low volatility as bullish and high volatility as bearish. For the
# leveraged ETFs this app centers on (TQQQ/SOXL), these are correlated views of
# the same underlying leverage, so a leveraged ETF gets nudged toward "Sell"
# through several channels. That is intentional, not a bug: this is a tool for a
# conservative investor learning the ropes, and penalizing leverage/volatility
# in the Buy/Hold/Sell signal is a feature. If the app later needs a purely
# directional signal, the cleaner move is to split volatility out into a
# separate per-symbol risk view (mirroring the portfolio risk grade) rather than
# to re-tune these weights.
WEIGHTS: dict[str, float] = {
    "rsi": 0.13,
    "macd": 0.13,
    "bollinger": 0.08,
    "sma_crossover": 0.13,
    "atr": 0.08,
    "beta": 0.13,
    "sharpe": 0.12,
    "sortino": 0.12,
    "max_drawdown": 0.08,
}


def _clamp(value: float) -> float:
    """Clamp to [-1, +1]."""
    return max(-1.0, min(1.0, value))


def normalize_signal(name: str, result: object) -> float:
    """Map an indicator result to a value in [-1, +1].

    +1 = strongly bullish, -1 = strongly bearish, 0 = neutral.
    All mappings use smooth linear interpolation (no discrete buckets).
    """
    if isinstance(result, RSIResult):
        # RSI 30 -> +1 (oversold/bullish), 50 -> 0, 70 -> -1 (overbought/bearish)
        return _clamp((50 - result.value) / 20)

    if isinstance(result, MACDResult):
        # Positive histogram = bullish, negative = bearish.
        # Normalize by signal line magnitude for scale independence.
        # Falls back to raw histogram sign if signal line is near zero.
        scale = max(abs(result.signal_line), abs(result.macd_line), 0.01)
        return _clamp(result.histogram / scale * 1.5)

    if isinstance(result, BollingerResult):
        # Smooth: width 0.02 (2%) -> +0.8 (tight, bullish),
        #         width 0.06 (6%) -> 0 (average),
        #         width 0.12 (12%) -> -1.0 (wide, bearish)
        # Linear interpolation centered on 0.06 typical width
        return _clamp((0.06 - result.width) / 0.06 * 1.0)

    if isinstance(result, SMACrossoverResult):
        # Golden cross = bullish, death cross = bearish.
        # Slower decay: full strength for 30 days, fades over 200 days, floor at 0.3
        if result.crossover_type == "golden_cross":
            days = result.days_since_cross or 0
            decay = max(0.3, 1.0 - max(0, days - 30) / 170)
            return decay
        elif result.crossover_type == "death_cross":
            days = result.days_since_cross or 0
            decay = max(0.3, 1.0 - max(0, days - 30) / 170)
            return -decay
        # No crossover: use SMA gap as a weaker directional signal
        gap = (result.sma_50 - result.sma_200) / result.sma_200 if result.sma_200 != 0 else 0
        return _clamp(gap * 10)  # 1% gap -> 0.1 signal

    if isinstance(result, ATRResult):
        # Smooth: ATR% 0.5 -> +0.6 (very stable),
        #         ATR% 2.0 -> 0 (average),
        #         ATR% 4.5 -> -0.8 (very volatile)
        return _clamp((2.0 - result.atr_percent) / 2.0 * 0.8)

    if isinstance(result, BetaResult):
        # Smooth: beta 0.5 -> +0.5 (defensive),
        #         beta 1.0 -> 0 (market),
        #         beta 2.0 -> -1.0 (very volatile)
        return _clamp((1.0 - result.value) * 1.0)

    if isinstance(result, SharpeResult):
        # Sharpe 2+ -> +1, 1 -> +0.5, 0 -> 0, -1 -> -0.5
        return _clamp(result.value / 2)

    if isinstance(result, SortinoResult):
        # Same shape as Sharpe. Sortino runs a bit higher for the same series
        # (smaller denominator), but 2+ -> strongly bullish still reads well.
        return _clamp(result.value / 2)

    if isinstance(result, MaxDrawdownResult):
        # Drawdown is a stability signal, not directional: a shallow historical
        # drawdown is mildly reassuring, a deep one is bearish.
        #   10% -> +0.43, 25% -> 0, 60% -> -1.0
        return _clamp((25 - result.value) / 35)

    raise ValueError(f"Unknown indicator: {name}")


def composite_score(
    results: dict[str, object],
) -> CompositeResult:
    """Compute weighted composite score from available indicator results.

    ``results`` maps indicator names (e.g. "rsi", "macd") to their result
    dataclasses.  Missing indicators are excluded and remaining weights are
    re-normalized.
    """
    contributions: dict[str, float] = {}
    directions: dict[str, str] = {}
    total_weight = 0.0
    weighted_sum = 0.0

    for name, weight in WEIGHTS.items():
        if name not in results:
            continue
        normalized = normalize_signal(name, results[name])
        contribution = normalized * weight
        contributions[name] = round(contribution, 4)
        if normalized > 0.05:
            directions[name] = "bullish"
        elif normalized < -0.05:
            directions[name] = "bearish"
        else:
            directions[name] = "neutral"
        weighted_sum += contribution
        total_weight += weight

    # Re-normalize if some indicators are missing
    if total_weight > 0 and total_weight < 1.0:
        score = weighted_sum / total_weight
    elif total_weight > 0:
        score = weighted_sum
    else:
        score = 0.0

    score = max(-1.0, min(1.0, score))

    # Signal classification — lower thresholds so moderate agreement triggers
    if score > 0.15:
        signal = "buy"
    elif score < -0.15:
        signal = "sell"
    else:
        signal = "hold"

    # Confidence: weight agreement more heavily than raw score magnitude
    agreement = _indicator_agreement(contributions)
    confidence = min(1.0, (abs(score) * 0.4 + agreement * 0.6))

    return CompositeResult(
        score=round(score, 4),
        signal=signal,
        confidence=round(confidence, 2),
        contributions=contributions,
        directions=directions,
    )


# Indicators that measure nearly the same thing and would otherwise cast
# duplicate "votes" when tallying agreement. Sortino is Sharpe with a
# downside-only denominator, so they almost always share a sign — counting both
# would inflate confidence. Each group is collapsed into a single averaged vote.
_CORRELATED_GROUPS: tuple[tuple[str, ...], ...] = (
    ("sharpe", "sortino"),
)


def _indicator_agreement(contributions: dict[str, float]) -> float:
    """Measure how much indicators agree (0 = split, 1 = unanimous).

    Correlated indicators (see ``_CORRELATED_GROUPS``) are merged into one vote
    first, so a near-duplicate signal doesn't count twice and inflate confidence.
    """
    if not contributions:
        return 0.0

    votes = dict(contributions)
    for group in _CORRELATED_GROUPS:
        present = [name for name in group if name in votes]
        if len(present) > 1:
            combined = sum(votes.pop(name) for name in present)
            # Represent the group as one vote at its net contribution.
            votes["+".join(present)] = combined

    signs = [1 if v > 0 else (-1 if v < 0 else 0) for v in votes.values()]
    non_zero = [s for s in signs if s != 0]
    if not non_zero:
        return 0.0
    majority = abs(sum(non_zero)) / len(non_zero)
    return majority
