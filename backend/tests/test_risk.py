"""Tests for portfolio risk math.

Uses deterministic data with known expected outputs — no DB, no mocking.
"""

import pytest

from risk.math import (
    concentration,
    correlation_matrix,
    effective_leverage,
    historical_stress_test,
    max_drawdown,
    portfolio_beta,
    risk_grade,
    worst_period,
)


# ---------------------------------------------------------------------------
# Concentration
# ---------------------------------------------------------------------------


class TestConcentration:
    def test_equal_weights_diversified(self):
        weights = [0.25, 0.25, 0.25, 0.25]
        sectors = ["Tech", "Healthcare", "Energy", "Finance"]
        result = concentration(weights, sectors)
        assert result.herfindahl_index == 0.25
        assert result.top_holding_pct == 25.0
        assert result.signal == "moderate"

    def test_single_holding(self):
        result = concentration([1.0], ["Tech"])
        assert result.herfindahl_index == 1.0
        assert result.top_holding_pct == 100.0
        assert result.signal == "highly_concentrated"

    def test_highly_diversified(self):
        weights = [0.1] * 10
        sectors = [f"Sector{i}" for i in range(10)]
        result = concentration(weights, sectors)
        assert result.herfindahl_index == 0.1
        assert result.signal == "diversified"

    def test_sector_aggregation(self):
        weights = [0.3, 0.3, 0.2, 0.2]
        sectors = ["Tech", "Tech", "Energy", "Energy"]
        result = concentration(weights, sectors)
        assert result.sector_breakdown["Tech"] == 60.0
        assert result.sector_breakdown["Energy"] == 40.0

    def test_mismatched_lengths(self):
        with pytest.raises(ValueError, match="same length"):
            concentration([0.5, 0.5], ["Tech"])

    def test_empty(self):
        with pytest.raises(ValueError, match="at least one"):
            concentration([], [])


# ---------------------------------------------------------------------------
# Correlation
# ---------------------------------------------------------------------------


class TestCorrelation:
    def test_identical_series(self):
        returns = {"A": [0.01, -0.02, 0.03, 0.01, -0.01] * 10,
                   "B": [0.01, -0.02, 0.03, 0.01, -0.01] * 10}
        result = correlation_matrix(returns)
        assert result.matrix["A"]["B"] == 1.0
        assert result.avg_pairwise == 1.0
        assert result.signal == "highly_correlated"

    def test_opposite_series(self):
        base = [0.01, -0.02, 0.03, 0.01, -0.01] * 10
        returns = {"A": base, "B": [-x for x in base]}
        result = correlation_matrix(returns)
        assert result.matrix["A"]["B"] == -1.0
        assert result.signal == "diversified"

    def test_uncorrelated(self):
        # Two series with no obvious relationship
        returns = {
            "A": [0.01, -0.02, 0.03, -0.01, 0.02, -0.03, 0.01, 0.02, -0.01, 0.03],
            "B": [0.02, 0.01, -0.01, 0.03, -0.02, 0.01, -0.03, 0.01, 0.02, -0.01],
        }
        result = correlation_matrix(returns)
        # Not perfectly correlated or anti-correlated
        assert -1.0 < result.avg_pairwise < 0.8

    def test_three_tickers(self):
        returns = {
            "A": [0.01, 0.02, -0.01] * 5,
            "B": [0.01, 0.02, -0.01] * 5,
            "C": [-0.01, -0.02, 0.01] * 5,
        }
        result = correlation_matrix(returns)
        # A and B identical, C is opposite
        assert result.matrix["A"]["B"] == 1.0
        assert result.matrix["A"]["C"] == -1.0
        assert result.max_pair[2] == 1.0

    def test_single_ticker(self):
        with pytest.raises(ValueError, match="at least 2"):
            correlation_matrix({"A": [0.01, 0.02]})


# ---------------------------------------------------------------------------
# Effective Leverage
# ---------------------------------------------------------------------------


class TestEffectiveLeverage:
    def test_all_unleveraged(self):
        result = effective_leverage([0.5, 0.5], [1.0, 1.0])
        assert result.value == 1.0
        assert result.leveraged_pct == 0.0
        assert result.signal == "none"

    def test_all_3x(self):
        result = effective_leverage([0.5, 0.5], [3.0, 3.0])
        assert result.value == 3.0
        assert result.leveraged_pct == 100.0
        assert result.signal == "extreme"

    def test_mixed(self):
        # 50% QQQ (1x) + 30% TQQQ (3x) + 20% SOXL (3x)
        result = effective_leverage([0.5, 0.3, 0.2], [1.0, 3.0, 3.0])
        assert result.value == 2.0
        assert result.leveraged_pct == 50.0
        assert result.signal == "high"

    def test_inverse_leverage(self):
        # SQQQ is -3x, abs value used
        result = effective_leverage([1.0], [-3.0])
        assert result.value == 3.0
        assert result.signal == "extreme"


# ---------------------------------------------------------------------------
# Portfolio Beta
# ---------------------------------------------------------------------------


class TestPortfolioBeta:
    def test_all_beta_one(self):
        result = portfolio_beta([0.5, 0.5], [1.0, 1.0])
        assert result.value == 1.0
        assert result.interpretation == "moves with market"

    def test_high_beta(self):
        # 50% beta 3.0 + 50% beta 1.0 = 2.0
        result = portfolio_beta([0.5, 0.5], [3.0, 1.0])
        assert result.value == 2.0
        assert result.interpretation == "more volatile than market"

    def test_very_high_beta(self):
        result = portfolio_beta([1.0], [3.5])
        assert result.value == 3.5
        assert result.interpretation == "significantly more volatile than market"

    def test_low_beta(self):
        result = portfolio_beta([1.0], [0.5])
        assert result.value == 0.5
        assert result.interpretation == "less volatile than market"


# ---------------------------------------------------------------------------
# Max Drawdown
# ---------------------------------------------------------------------------


class TestMaxDrawdown:
    def test_known_drawdown(self):
        # Portfolio goes 100 -> 80 -> 60 -> 90 -> 100
        values = [100.0, 80.0, 60.0, 90.0, 100.0]
        dates = ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]
        result = max_drawdown(values, dates)
        assert result.value == 40.0  # 100 -> 60 = 40%
        assert result.worst_start == "2024-01-01"
        assert result.worst_end == "2024-01-03"
        assert result.signal == "high_risk"

    def test_no_drawdown(self):
        values = [100.0, 110.0, 120.0, 130.0]
        dates = ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"]
        result = max_drawdown(values, dates)
        assert result.value == 0.0
        assert result.signal == "low_risk"

    def test_extreme_drawdown(self):
        values = [100.0, 40.0]
        dates = ["2024-01-01", "2024-01-02"]
        result = max_drawdown(values, dates)
        assert result.value == 60.0
        assert result.signal == "extreme_risk"

    def test_too_few_points(self):
        with pytest.raises(ValueError, match="at least 2"):
            max_drawdown([100.0], ["2024-01-01"])


# ---------------------------------------------------------------------------
# Historical Stress Test
# ---------------------------------------------------------------------------


class TestHistoricalStressTest:
    def test_basic_scenario(self):
        # QQQ drops 20%, TQQQ drops 60% (3x leverage)
        holdings_prices = {
            "QQQ": {"2020-02-19": 100.0, "2020-03-23": 80.0},
            "TQQQ": {"2020-02-19": 100.0, "2020-03-23": 40.0},
        }
        result = historical_stress_test(
            holdings_prices=holdings_prices,
            weights=[0.5, 0.5],
            tickers=["QQQ", "TQQQ"],
            start_date="2020-02-19",
            end_date="2020-03-23",
            scenario_name="COVID Crash",
            portfolio_value=10000.0,
        )
        assert result.portfolio_impact_pct == -40.0  # 50% * -20% + 50% * -60%
        assert result.portfolio_impact_dollar == -4000.0
        assert len(result.holdings_impact) == 2
        assert result.holdings_impact[0]["return_pct"] == -20.0
        assert result.holdings_impact[1]["return_pct"] == -60.0

    def test_missing_ticker_data_renormalizes(self):
        """Missing holdings should not mute the portfolio impact."""
        holdings_prices = {
            "QQQ": {"2020-02-19": 100.0, "2020-03-23": 80.0},
        }
        result = historical_stress_test(
            holdings_prices=holdings_prices,
            weights=[0.5, 0.5],
            tickers=["QQQ", "NEW_STOCK"],
            start_date="2020-02-19",
            end_date="2020-03-23",
            scenario_name="COVID Crash",
            portfolio_value=10000.0,
        )
        assert result.holdings_impact[1]["return_pct"] is None
        assert result.holdings_impact[1]["note"] == "no data for this period"
        # Renormalized: QQQ is the only covered holding, so portfolio impact
        # should reflect QQQ's full -20%, not -10% (half-weighted)
        assert result.portfolio_impact_pct == -20.0
        assert result.coverage_pct == 50.0

    def test_positive_scenario(self):
        holdings_prices = {
            "QQQ": {"2020-03-23": 50.0, "2020-08-18": 75.0},
        }
        result = historical_stress_test(
            holdings_prices=holdings_prices,
            weights=[1.0],
            tickers=["QQQ"],
            start_date="2020-03-23",
            end_date="2020-08-18",
            scenario_name="2020 Recovery",
            portfolio_value=5000.0,
        )
        assert result.portfolio_impact_pct == 50.0
        assert result.portfolio_impact_dollar == 2500.0


# ---------------------------------------------------------------------------
# Worst Period
# ---------------------------------------------------------------------------


class TestWorstPeriod:
    def test_finds_worst_window(self):
        # 10 days, big drop in the middle
        values = [100, 100, 100, 80, 60, 50, 55, 60, 70, 80, 90]
        dates = [f"2024-01-{i+1:02d}" for i in range(len(values))]
        result = worst_period(values, dates, window_days=3)
        assert result.portfolio_impact_pct < 0
        assert "Worst 3-Day" in result.scenario_name

    def test_too_few_points(self):
        with pytest.raises(ValueError, match="at least"):
            worst_period([100, 90, 80], ["d1", "d2", "d3"], window_days=5)


# ---------------------------------------------------------------------------
# Risk Grade
# ---------------------------------------------------------------------------


class TestRiskGrade:
    def _make_conc(self, hhi, top_pct):
        return concentration(
            [top_pct / 100] + [(1 - top_pct / 100) / 3] * 3,
            ["Tech", "Health", "Energy", "Finance"],
        )

    def test_safe_portfolio(self):
        """Diversified, unleveraged, low beta, small drawdown."""
        from risk.models import (
            ConcentrationResult, CorrelationResult,
            EffectiveLeverageResult, PortfolioBetaResult, MaxDrawdownResult,
        )
        conc = ConcentrationResult(0.08, 20.0, {"A": 40.0, "B": 30.0, "C": 30.0}, "diversified")
        corr = CorrelationResult({}, 0.2, ("A", "B", 0.3), "diversified")
        lev = EffectiveLeverageResult(1.0, 0.0, "none")
        beta_r = PortfolioBetaResult(0.9, "moves with market")
        dd = MaxDrawdownResult(8.0, "2024-01-01", "2024-01-15", 12.0, "low_risk")

        result = risk_grade(conc, corr, lev, beta_r, dd)
        assert result.grade in ("A", "B")
        assert result.score >= 65

    def test_risky_portfolio(self):
        """Concentrated, leveraged 3x, high beta, big drawdown — like TQQQ+SOXL."""
        from risk.models import (
            ConcentrationResult, CorrelationResult,
            EffectiveLeverageResult, PortfolioBetaResult, MaxDrawdownResult,
        )
        conc = ConcentrationResult(0.50, 60.0, {"Tech": 60.0, "Semis": 40.0}, "highly_concentrated")
        corr = CorrelationResult({}, 0.95, ("TQQQ", "SOXL", 0.97), "highly_correlated")
        lev = EffectiveLeverageResult(3.0, 100.0, "extreme")
        beta_r = PortfolioBetaResult(3.2, "significantly more volatile than market")
        dd = MaxDrawdownResult(65.0, "2020-02-19", "2020-03-23", 55.0, "extreme_risk")

        result = risk_grade(conc, corr, lev, beta_r, dd)
        assert result.grade in ("D", "F")
        assert result.score < 35

    def test_components_visible(self):
        """Grade response includes per-component breakdown."""
        from risk.models import (
            ConcentrationResult, EffectiveLeverageResult,
            PortfolioBetaResult, MaxDrawdownResult,
        )
        conc = ConcentrationResult(0.25, 40.0, {"Tech": 100.0}, "moderate")
        lev = EffectiveLeverageResult(2.0, 50.0, "high")
        beta_r = PortfolioBetaResult(1.5, "more volatile than market")
        dd = MaxDrawdownResult(25.0, "2022-01-01", "2022-06-01", 20.0, "moderate_risk")

        result = risk_grade(conc, None, lev, beta_r, dd)
        assert "concentration" in result.components
        assert "correlation" in result.components
        assert "leverage" in result.components
        assert "beta" in result.components
        assert "drawdown" in result.components
        # Each component has penalty, max_penalty, reason
        for comp in result.components.values():
            assert "penalty" in comp
            assert "max_penalty" in comp
            assert "reason" in comp

    def test_no_correlation_single_holding(self):
        """Single holding — correlation penalty should be 0."""
        from risk.models import (
            ConcentrationResult, EffectiveLeverageResult,
            PortfolioBetaResult, MaxDrawdownResult,
        )
        conc = ConcentrationResult(1.0, 100.0, {"Tech": 100.0}, "highly_concentrated")
        lev = EffectiveLeverageResult(1.0, 0.0, "none")
        beta_r = PortfolioBetaResult(1.0, "moves with market")
        dd = MaxDrawdownResult(15.0, "2024-01-01", "2024-02-01", 15.0, "moderate_risk")

        result = risk_grade(conc, None, lev, beta_r, dd)
        assert result.components["correlation"]["penalty"] == 0.0
