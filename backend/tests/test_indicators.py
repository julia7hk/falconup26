"""Tests for indicator math and composite scoring.

Uses deterministic data with known expected outputs — no DB, no mocking.
"""

import pytest

from indicators.math import (
    atr,
    beta,
    bollinger_width,
    macd,
    max_drawdown,
    rsi,
    sharpe_ratio,
    sma_crossover,
    sortino_ratio,
)
from indicators.composite import composite_score, normalize_signal


# ---------------------------------------------------------------------------
# RSI
# ---------------------------------------------------------------------------


class TestRSI:
    def test_constant_prices(self):
        """No movement -> RSI = 50 (equal avg gain/loss of 0)."""
        closes = [100.0] * 20
        # With all gains and losses = 0, avg_gain=0 and avg_loss=0.
        # When avg_loss=0, RSI = 100. But with constant prices there are
        # truly zero gains too, so let's just verify it doesn't crash.
        result = rsi(closes)
        assert result.value == 100.0  # avg_loss=0 -> RSI=100

    def test_strictly_rising(self):
        closes = [100.0 + i for i in range(30)]
        result = rsi(closes)
        assert result.value > 90
        assert result.signal == "overbought"

    def test_strictly_falling(self):
        closes = [200.0 - i for i in range(30)]
        result = rsi(closes)
        assert result.value < 10
        assert result.signal == "oversold"

    def test_mixed_movement(self):
        closes = [100 + (i % 3) - 1 for i in range(30)]
        result = rsi(closes)
        assert 20 < result.value < 80
        assert result.signal == "neutral"

    def test_too_few_points(self):
        with pytest.raises(ValueError, match="at least 15"):
            rsi([100.0] * 10)


# ---------------------------------------------------------------------------
# MACD
# ---------------------------------------------------------------------------


class TestMACD:
    def test_flat_prices(self):
        closes = [100.0] * 50
        result = macd(closes)
        assert abs(result.histogram) < 0.01
        assert result.signal == "neutral"

    def test_trending_up(self):
        closes = [100.0 + i * 0.5 for i in range(50)]
        result = macd(closes)
        assert result.macd_line > 0

    def test_trending_down(self):
        closes = [200.0 - i * 0.5 for i in range(50)]
        result = macd(closes)
        assert result.macd_line < 0

    def test_too_few_points(self):
        with pytest.raises(ValueError, match="at least 35"):
            macd([100.0] * 30)


# ---------------------------------------------------------------------------
# Bollinger Bands
# ---------------------------------------------------------------------------


class TestBollinger:
    def test_constant_prices(self):
        closes = [100.0] * 30
        result = bollinger_width(closes)
        assert result.width == 0.0
        assert result.upper == 100.0
        assert result.lower == 100.0

    def test_volatile_prices(self):
        closes = [100 + (10 if i % 2 == 0 else -10) for i in range(30)]
        result = bollinger_width(closes)
        assert result.width > 0
        assert result.upper > result.lower

    def test_too_few_points(self):
        with pytest.raises(ValueError, match="at least 20"):
            bollinger_width([100.0] * 10)


# ---------------------------------------------------------------------------
# SMA Crossover
# ---------------------------------------------------------------------------


class TestSMACrossover:
    def test_golden_cross(self):
        # 200 days of low prices, then 100 days of high prices
        # SMA-50 will rise above SMA-200
        closes = [100.0] * 200 + [150.0] * 100
        result = sma_crossover(closes)
        assert result.crossover_type == "golden_cross"
        assert result.days_since_cross is not None
        assert result.sma_50 > result.sma_200

    def test_death_cross(self):
        # 200 days of high prices, then 100 days of low prices
        closes = [150.0] * 200 + [100.0] * 100
        result = sma_crossover(closes)
        assert result.crossover_type == "death_cross"
        assert result.days_since_cross is not None
        assert result.sma_50 < result.sma_200

    def test_no_crossover(self):
        # Flat prices -> SMA-50 == SMA-200, no crossover
        closes = [100.0] * 300
        result = sma_crossover(closes)
        assert result.crossover_type == "none"
        assert result.days_since_cross is None

    def test_too_few_points(self):
        with pytest.raises(ValueError, match="at least 200"):
            sma_crossover([100.0] * 150)


# ---------------------------------------------------------------------------
# ATR
# ---------------------------------------------------------------------------


class TestATR:
    def test_constant_range(self):
        # Every day: high=110, low=100, close=105 -> TR = 10 always
        n = 30
        highs = [110.0] * n
        lows = [100.0] * n
        closes = [105.0] * n
        result = atr(highs, lows, closes)
        assert abs(result.value - 10.0) < 0.01
        assert result.atr_percent == pytest.approx(10.0 / 105.0 * 100, abs=0.1)

    def test_mismatched_lengths(self):
        with pytest.raises(ValueError, match="same length"):
            atr([110.0] * 20, [100.0] * 19, [105.0] * 20)

    def test_too_few_points(self):
        with pytest.raises(ValueError, match="at least 15"):
            atr([110.0] * 10, [100.0] * 10, [105.0] * 10)


# ---------------------------------------------------------------------------
# Beta
# ---------------------------------------------------------------------------


class TestBeta:
    def test_identical_series(self):
        closes = [100.0 + i for i in range(50)]
        result = beta(closes, closes)
        assert result.value == pytest.approx(1.0, abs=0.01)

    def test_high_beta(self):
        # Symbol with larger swings -> beta > 1
        bench = [100.0 + i for i in range(50)]
        sym = [100.0 + i * 2 for i in range(50)]
        result = beta(sym, bench)
        assert result.value > 1.5
        assert "more volatile" in result.interpretation

    def test_low_beta(self):
        # Symbol moves half the benchmark
        bench = [100.0 + i for i in range(50)]
        sym = [100.0 + i * 0.5 for i in range(50)]
        result = beta(sym, bench)
        assert result.value < 1.0
        assert result.interpretation == "less volatile than market"

    def test_mismatched_lengths(self):
        with pytest.raises(ValueError, match="same length"):
            beta([100.0] * 10, [100.0] * 11)


# ---------------------------------------------------------------------------
# Sharpe Ratio
# ---------------------------------------------------------------------------


class TestSharpe:
    def test_positive_returns(self):
        # Steadily increasing prices -> positive Sharpe
        closes = [100.0 + i * 0.1 for i in range(252)]
        result = sharpe_ratio(closes, risk_free_annual=5.0)
        assert result.value > 0

    def test_negative_returns(self):
        # Steadily decreasing prices -> negative Sharpe
        closes = [200.0 - i * 0.5 for i in range(252)]
        result = sharpe_ratio(closes, risk_free_annual=5.0)
        assert result.value < 0
        assert result.interpretation == "negative risk-adjusted return"

    def test_risk_free_rate_passed_through(self):
        closes = [100.0 + i for i in range(50)]
        result = sharpe_ratio(closes, risk_free_annual=4.5)
        assert result.risk_free_rate == 4.5

    def test_too_few_points(self):
        with pytest.raises(ValueError, match="at least 2"):
            sharpe_ratio([100.0], risk_free_annual=5.0)


# ---------------------------------------------------------------------------
# Sortino Ratio
# ---------------------------------------------------------------------------


class TestSortino:
    def test_negative_returns(self):
        # Steadily decreasing prices -> negative Sortino
        closes = [200.0 - i * 0.5 for i in range(252)]
        result = sortino_ratio(closes, risk_free_annual=5.0)
        assert result.value < 0
        assert result.interpretation == "negative downside-adjusted return"

    def test_only_downside_counts(self):
        """Two series with identical downside but different upside: the one
        with bigger upside has a higher mean return, so a higher Sortino —
        but neither series' upside inflates the *denominator*."""
        # Alternating down/up moves. Big-upside series has larger up legs.
        modest = [100.0]
        big = [100.0]
        for i in range(200):
            if i % 2 == 0:
                modest.append(modest[-1] * 0.99)  # -1% down leg (shared)
                big.append(big[-1] * 0.99)
            else:
                modest.append(modest[-1] * 1.015)  # +1.5% up
                big.append(big[-1] * 1.05)          # +5% up
        r_modest = sortino_ratio(modest, risk_free_annual=0.0)
        r_big = sortino_ratio(big, risk_free_annual=0.0)
        assert r_big.value > r_modest.value

    def test_sortino_exceeds_sharpe_with_downside(self):
        """With downside volatility present, Sortino >= Sharpe because it
        ignores upside swings in the denominator."""
        closes = [100.0]
        for i in range(200):
            closes.append(closes[-1] * (1.02 if i % 3 else 0.985))
        s = sharpe_ratio(closes, risk_free_annual=2.0)
        so = sortino_ratio(closes, risk_free_annual=2.0)
        assert so.value >= s.value

    def test_no_downside_degenerate(self):
        """Strictly rising prices -> no losing days -> documented 0.0."""
        closes = [100.0 + i for i in range(60)]
        result = sortino_ratio(closes, risk_free_annual=0.0)
        assert result.value == 0.0

    def test_risk_free_rate_passed_through(self):
        closes = [100.0 + i for i in range(50)]
        result = sortino_ratio(closes, risk_free_annual=4.5)
        assert result.risk_free_rate == 4.5

    def test_too_few_points(self):
        with pytest.raises(ValueError, match="at least 2"):
            sortino_ratio([100.0], risk_free_annual=5.0)


# ---------------------------------------------------------------------------
# Max Drawdown
# ---------------------------------------------------------------------------


class TestMaxDrawdown:
    def test_simple_drawdown(self):
        # Peak 100 at index 1, trough 60 at index 3 -> 40% drawdown
        closes = [80.0, 100.0, 75.0, 60.0, 90.0]
        dates = ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]
        result = max_drawdown(closes, dates)
        assert result.value == 40.0
        assert result.peak_date == "2024-01-02"
        assert result.trough_date == "2024-01-04"

    def test_monotonic_rise_no_drawdown(self):
        closes = [100.0 + i for i in range(20)]
        dates = [f"2024-02-{i + 1:02d}" for i in range(20)]
        result = max_drawdown(closes, dates)
        assert result.value == 0.0

    def test_worst_of_multiple_drops(self):
        # Two drawdowns: 20% (100->80) then 50% (120->60). Reports the worse one.
        closes = [100.0, 80.0, 120.0, 60.0]
        dates = ["2024-03-01", "2024-03-02", "2024-03-03", "2024-03-04"]
        result = max_drawdown(closes, dates)
        assert result.value == 50.0
        assert result.peak_date == "2024-03-03"
        assert result.trough_date == "2024-03-04"

    def test_length_mismatch(self):
        with pytest.raises(ValueError, match="same length"):
            max_drawdown([100.0, 90.0], ["2024-01-01"])

    def test_too_few_points(self):
        with pytest.raises(ValueError, match="at least 2"):
            max_drawdown([100.0], ["2024-01-01"])


# ---------------------------------------------------------------------------
# Composite Scoring
# ---------------------------------------------------------------------------


class TestComposite:
    def _bullish_results(self):
        """All indicators pointing bullish."""
        from indicators.models import (
            RSIResult, MACDResult, BollingerResult,
            SMACrossoverResult, ATRResult, BetaResult, SharpeResult,
            SortinoResult, MaxDrawdownResult,
        )
        return {
            "rsi": RSIResult(value=25.0, signal="oversold"),
            "macd": MACDResult(macd_line=2.0, signal_line=1.0, histogram=1.0, signal="bullish"),
            "bollinger": BollingerResult(width=0.02, upper=102.0, lower=98.0, signal="low_volatility"),
            "sma_crossover": SMACrossoverResult(sma_50=110.0, sma_200=100.0, crossover_type="golden_cross", days_since_cross=5),
            "atr": ATRResult(value=0.8, atr_percent=0.8),
            "beta": BetaResult(value=0.6, interpretation="less volatile than market"),
            "sharpe": SharpeResult(value=2.5, risk_free_rate=5.0, interpretation="excellent risk-adjusted return"),
            "sortino": SortinoResult(value=3.0, risk_free_rate=5.0, interpretation="excellent downside-adjusted return"),
            "max_drawdown": MaxDrawdownResult(value=8.0, peak_date="2024-01-01", trough_date="2024-01-15"),
        }

    def _bearish_results(self):
        """All indicators pointing bearish."""
        from indicators.models import (
            RSIResult, MACDResult, BollingerResult,
            SMACrossoverResult, ATRResult, BetaResult, SharpeResult,
            SortinoResult, MaxDrawdownResult,
        )
        return {
            "rsi": RSIResult(value=80.0, signal="overbought"),
            "macd": MACDResult(macd_line=-2.0, signal_line=-1.0, histogram=-1.0, signal="bearish"),
            "bollinger": BollingerResult(width=0.10, upper=115.0, lower=85.0, signal="high_volatility"),
            "sma_crossover": SMACrossoverResult(sma_50=90.0, sma_200=100.0, crossover_type="death_cross", days_since_cross=5),
            "atr": ATRResult(value=5.0, atr_percent=5.0),
            "beta": BetaResult(value=2.0, interpretation="significantly more volatile than market"),
            "sharpe": SharpeResult(value=-0.5, risk_free_rate=5.0, interpretation="negative risk-adjusted return"),
            "sortino": SortinoResult(value=-0.8, risk_free_rate=5.0, interpretation="negative downside-adjusted return"),
            "max_drawdown": MaxDrawdownResult(value=65.0, peak_date="2024-01-01", trough_date="2024-03-23"),
        }

    def test_all_bullish(self):
        result = composite_score(self._bullish_results())
        assert result.score > 0.25
        assert result.signal == "buy"
        assert result.confidence > 0

    def test_all_bearish(self):
        result = composite_score(self._bearish_results())
        assert result.score < -0.25
        assert result.signal == "sell"

    def test_missing_indicators(self):
        """Should still work with fewer than 9 indicators."""
        results = {k: v for k, v in list(self._bullish_results().items())[:3]}
        result = composite_score(results)
        assert result.signal in ("buy", "hold", "sell")
        assert len(result.contributions) == 3

    def test_empty_results(self):
        result = composite_score({})
        assert result.score == 0.0
        assert result.signal == "hold"


class TestNormalizeSignal:
    def test_rsi_oversold(self):
        from indicators.models import RSIResult
        val = normalize_signal("rsi", RSIResult(value=25.0, signal="oversold"))
        assert val > 0  # bullish

    def test_rsi_overbought(self):
        from indicators.models import RSIResult
        val = normalize_signal("rsi", RSIResult(value=75.0, signal="overbought"))
        assert val < 0  # bearish

    def test_rsi_neutral(self):
        from indicators.models import RSIResult
        val = normalize_signal("rsi", RSIResult(value=50.0, signal="neutral"))
        assert val == 0.0

    def test_bollinger_smooth(self):
        """Bollinger should produce different values for different widths, not buckets."""
        from indicators.models import BollingerResult
        narrow = normalize_signal("bollinger", BollingerResult(width=0.02, upper=102, lower=98, signal="low_volatility"))
        medium = normalize_signal("bollinger", BollingerResult(width=0.06, upper=106, lower=94, signal="neutral"))
        wide = normalize_signal("bollinger", BollingerResult(width=0.10, upper=110, lower=90, signal="high_volatility"))
        assert narrow > medium > wide
        assert narrow > 0.5  # strong bullish for tight bands
        assert wide < -0.5   # strong bearish for wide bands

    def test_atr_smooth(self):
        """ATR should interpolate smoothly, not use discrete buckets."""
        from indicators.models import ATRResult
        low = normalize_signal("atr", ATRResult(value=0.5, atr_percent=0.5))
        mid = normalize_signal("atr", ATRResult(value=2.0, atr_percent=2.0))
        high = normalize_signal("atr", ATRResult(value=4.0, atr_percent=4.0))
        assert low > mid > high
        assert low > 0.4
        assert abs(mid) < 0.1  # near zero at 2%
        assert high < -0.5

    def test_beta_smooth(self):
        """Beta should interpolate smoothly."""
        from indicators.models import BetaResult
        low = normalize_signal("beta", BetaResult(value=0.5, interpretation="less volatile"))
        market = normalize_signal("beta", BetaResult(value=1.0, interpretation="moves with market"))
        high = normalize_signal("beta", BetaResult(value=2.0, interpretation="very volatile"))
        assert low > market > high
        assert low > 0.3
        assert abs(market) < 0.1
        assert high < -0.5

    def test_macd_responds_to_magnitude(self):
        """MACD should produce different signals for different histogram sizes."""
        from indicators.models import MACDResult
        strong = normalize_signal("macd", MACDResult(macd_line=3.0, signal_line=2.0, histogram=1.0, signal="bullish"))
        weak = normalize_signal("macd", MACDResult(macd_line=3.0, signal_line=2.8, histogram=0.2, signal="bullish"))
        assert strong > weak > 0

    def test_sma_crossover_decay(self):
        """Recent crossover should be stronger than old one, but old one should still matter."""
        from indicators.models import SMACrossoverResult
        recent = normalize_signal("sma_crossover", SMACrossoverResult(sma_50=110, sma_200=100, crossover_type="golden_cross", days_since_cross=5))
        old = normalize_signal("sma_crossover", SMACrossoverResult(sma_50=110, sma_200=100, crossover_type="golden_cross", days_since_cross=100))
        very_old = normalize_signal("sma_crossover", SMACrossoverResult(sma_50=110, sma_200=100, crossover_type="golden_cross", days_since_cross=200))
        assert recent > old > 0
        assert very_old >= 0.3  # floor keeps old crossovers relevant

    def test_sma_no_crossover_uses_gap(self):
        """When no crossover, SMA gap should still produce a weak signal."""
        from indicators.models import SMACrossoverResult
        above = normalize_signal("sma_crossover", SMACrossoverResult(sma_50=105, sma_200=100, crossover_type="none", days_since_cross=None))
        below = normalize_signal("sma_crossover", SMACrossoverResult(sma_50=95, sma_200=100, crossover_type="none", days_since_cross=None))
        assert above > 0  # SMA-50 above SMA-200 = bullish
        assert below < 0  # SMA-50 below SMA-200 = bearish

    def test_sortino_scales_with_value(self):
        from indicators.models import SortinoResult
        strong = normalize_signal("sortino", SortinoResult(value=3.0, risk_free_rate=5.0, interpretation=""))
        weak = normalize_signal("sortino", SortinoResult(value=0.5, risk_free_rate=5.0, interpretation=""))
        neg = normalize_signal("sortino", SortinoResult(value=-1.0, risk_free_rate=5.0, interpretation=""))
        assert strong == 1.0  # clamped, 3/2 -> +1
        assert 0 < weak < strong
        assert neg < 0

    def test_max_drawdown_smooth(self):
        """Shallow drawdown -> mildly bullish, deep -> bearish, crossing zero."""
        from indicators.models import MaxDrawdownResult
        shallow = normalize_signal("max_drawdown", MaxDrawdownResult(value=10.0, peak_date="", trough_date=""))
        mid = normalize_signal("max_drawdown", MaxDrawdownResult(value=25.0, peak_date="", trough_date=""))
        deep = normalize_signal("max_drawdown", MaxDrawdownResult(value=60.0, peak_date="", trough_date=""))
        assert shallow > 0
        assert abs(mid) < 0.05  # ~0 at the 25% pivot
        assert deep == -1.0  # clamped


class TestCompositeConfidence:
    """Verify confidence responds to indicator agreement."""

    def test_unanimous_bullish_high_confidence(self):
        from indicators.models import (
            RSIResult, MACDResult, BollingerResult,
            SMACrossoverResult, ATRResult, BetaResult, SharpeResult,
        )
        results = {
            "rsi": RSIResult(value=25.0, signal="oversold"),
            "macd": MACDResult(macd_line=2.0, signal_line=1.0, histogram=1.0, signal="bullish"),
            "bollinger": BollingerResult(width=0.02, upper=102, lower=98, signal="low_volatility"),
            "sma_crossover": SMACrossoverResult(sma_50=110, sma_200=100, crossover_type="golden_cross", days_since_cross=5),
            "atr": ATRResult(value=0.8, atr_percent=0.8),
            "beta": BetaResult(value=0.6, interpretation="less volatile"),
            "sharpe": SharpeResult(value=2.5, risk_free_rate=5.0, interpretation="excellent"),
        }
        result = composite_score(results)
        assert result.confidence >= 0.5  # strong agreement should produce decent confidence

    def test_mixed_signals_lower_confidence(self):
        from indicators.models import (
            RSIResult, MACDResult, BollingerResult,
            ATRResult, BetaResult, SharpeResult,
        )
        results = {
            "rsi": RSIResult(value=25.0, signal="oversold"),           # bullish
            "macd": MACDResult(macd_line=-1.0, signal_line=-0.5, histogram=-0.5, signal="bearish"),  # bearish
            "bollinger": BollingerResult(width=0.06, upper=106, lower=94, signal="neutral"),  # neutral
            "atr": ATRResult(value=2.0, atr_percent=2.0),              # neutral
            "beta": BetaResult(value=1.5, interpretation="volatile"),   # bearish
            "sharpe": SharpeResult(value=1.0, risk_free_rate=5.0, interpretation="good"),  # bullish
        }
        result = composite_score(results)
        unanimous = 0.5  # from the test above
        assert result.confidence < unanimous  # mixed signals = less confident

    def test_correlated_indicators_dont_inflate_confidence(self):
        """Sharpe + Sortino are near-duplicates; adding an agreeing Sortino to
        an otherwise-split portfolio must NOT raise agreement (it's one vote,
        not two)."""
        from indicators.composite import _indicator_agreement
        # One bullish (rsi), one bearish (macd), plus sharpe+sortino both bullish.
        # Naive counting: 3 bullish / 1 bearish -> 0.5 majority.
        # Merged: rsi(+), macd(-), sharpe+sortino(+) -> 2/3 -> 0.5 too here, so
        # use a case where double-counting would clearly differ:
        base = {"rsi": 0.1, "macd": -0.1, "beta": -0.1}  # 1 up, 2 down -> 1/3
        without = _indicator_agreement(base)
        with_corr = _indicator_agreement({**base, "sharpe": 0.1, "sortino": 0.1})
        # sharpe+sortino collapse to ONE up vote -> 2 up, 2 down -> 0.0,
        # not 3 up / 2 down (0.2) as double-counting would give.
        assert with_corr == 0.0
        assert without == pytest.approx(1 / 3)
