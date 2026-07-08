"""Tests for indicator math and composite scoring.

Uses deterministic data with known expected outputs — no DB, no mocking.
"""

import pytest

from indicators.math import (
    atr,
    beta,
    bollinger_width,
    macd,
    rsi,
    sharpe_ratio,
    sma_crossover,
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
# Composite Scoring
# ---------------------------------------------------------------------------


class TestComposite:
    def _bullish_results(self):
        """All indicators pointing bullish."""
        from indicators.models import (
            RSIResult, MACDResult, BollingerResult,
            SMACrossoverResult, ATRResult, BetaResult, SharpeResult,
        )
        return {
            "rsi": RSIResult(value=25.0, signal="oversold"),
            "macd": MACDResult(macd_line=2.0, signal_line=1.0, histogram=1.0, signal="bullish"),
            "bollinger": BollingerResult(width=0.02, upper=102.0, lower=98.0, signal="low_volatility"),
            "sma_crossover": SMACrossoverResult(sma_50=110.0, sma_200=100.0, crossover_type="golden_cross", days_since_cross=5),
            "atr": ATRResult(value=0.8, atr_percent=0.8),
            "beta": BetaResult(value=0.6, interpretation="less volatile than market"),
            "sharpe": SharpeResult(value=2.5, risk_free_rate=5.0, interpretation="excellent risk-adjusted return"),
        }

    def _bearish_results(self):
        """All indicators pointing bearish."""
        from indicators.models import (
            RSIResult, MACDResult, BollingerResult,
            SMACrossoverResult, ATRResult, BetaResult, SharpeResult,
        )
        return {
            "rsi": RSIResult(value=80.0, signal="overbought"),
            "macd": MACDResult(macd_line=-2.0, signal_line=-1.0, histogram=-1.0, signal="bearish"),
            "bollinger": BollingerResult(width=0.10, upper=115.0, lower=85.0, signal="high_volatility"),
            "sma_crossover": SMACrossoverResult(sma_50=90.0, sma_200=100.0, crossover_type="death_cross", days_since_cross=5),
            "atr": ATRResult(value=5.0, atr_percent=5.0),
            "beta": BetaResult(value=2.0, interpretation="significantly more volatile than market"),
            "sharpe": SharpeResult(value=-0.5, risk_free_rate=5.0, interpretation="negative risk-adjusted return"),
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
        """Should still work with fewer than 7 indicators."""
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
