"""Tests for GET /api/portfolio/risk/explain (auth + payload shape).

Deterministic explainer endpoint — no network. Reuses the whatif test's mock
session + fake fetcher (same _fetch_market_data plumbing). The math is covered
in test_explainer_templates; here we check auth-gating, the available/
unavailable branches, and that the explanation describes the same grade the
/risk endpoint computes from the same data.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import llm_explainer
from auth import get_current_user
from db import get_session
from main import app
from tests.test_api_whatif import (
    FAKE_USER,
    QQQ,
    TQQQ,
    SpyRow,
    _mock_session,
    _patched_fetcher,
    _price_series,
)

client = TestClient(app)


def _override(session):
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER

    async def _gen():
        yield session

    app.dependency_overrides[get_session] = _gen


def _get(path="/api/portfolio/risk/explain"):
    with patch("routers.risk.get_price_fetcher", _patched_fetcher):
        return client.get(path)


# 90 aligned daily closes each for the two holdings + SPY — enough for betas
# (needs 60 aligned days) and drawdown/grade (needs 60 portfolio values).
_FULL_HISTORY = (
    _price_series("QQQ", 90) + _price_series("TQQQ", 90) + _price_series("SPY", 90)
)


@pytest.fixture(autouse=True)
def _llm_off(monkeypatch):
    # Keep this endpoint suite hermetic: force the LLM enrichment path off so no
    # test makes a real Groq call (a GROQ_API_KEY may be present in the dev
    # environment). The LLM-path behavior is covered in test_explainer_enrich.py.
    monkeypatch.setattr(llm_explainer.client, "generate", lambda _ex: None)


class TestRiskExplain:
    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_requires_auth(self):
        # No auth override -> get_current_user raises 401 before the body runs.
        async def _gen():
            yield _mock_session([QQQ, TQQQ])

        app.dependency_overrides[get_session] = _gen
        resp = client.get("/api/portfolio/risk/explain")
        assert resp.status_code == 401

    def test_no_holdings_unavailable(self):
        _override(_mock_session([]))
        resp = _get()
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is False
        assert data["explanation"] is None
        assert "holdings" in data["message"].lower()
        assert data["computed_at"]

    def test_insufficient_history_unavailable(self):
        # Held holdings but no price history -> no grade, distinct message.
        _override(_mock_session([QQQ, TQQQ], price_rows=[]))
        resp = _get()
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is False
        assert data["explanation"] is None
        assert "history" in data["message"].lower()

    def test_available_payload_shape(self):
        _override(_mock_session([QQQ, TQQQ], spy=True, price_rows=_FULL_HISTORY))
        resp = _get()
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert data["message"] is None
        ex = data["explanation"]
        assert set(ex) >= {
            "grade",
            "score",
            "headline",
            "overview",
            "components",
            "disclaimer",
        }
        assert ex["grade"] in {"A", "B", "C", "D", "F"}
        assert "not financial advice" in ex["disclaimer"].lower()
        assert len(ex["components"]) >= 1
        for s in ex["components"]:
            assert {"key", "label", "penalty", "max_penalty", "severity",
                    "meaning", "detail"} <= set(s)

    def test_matches_risk_endpoint_grade(self):
        # The explanation must describe the same grade /risk reports for the
        # same data — they share _compute_risk_metrics, this guards the wiring.
        _override(_mock_session([QQQ, TQQQ], spy=True, price_rows=_FULL_HISTORY))
        risk = _get("/api/portfolio/risk").json()
        _override(_mock_session([QQQ, TQQQ], spy=True, price_rows=_FULL_HISTORY))
        explain = _get().json()
        assert risk["risk_grade"] is not None
        assert explain["explanation"]["grade"] == risk["risk_grade"]["grade"]
        assert explain["explanation"]["score"] == risk["risk_grade"]["score"]

    def test_risk_endpoint_carries_inline_explanation(self):
        # /risk folds the deterministic explanation in so the dashboard renders
        # instantly. The standalone endpoint is the PR2 LLM path and adds a
        # `source` marker (deterministic here — no API key in tests). With the
        # LLM off, the two must otherwise match exactly, guarding the wiring.
        _override(_mock_session([QQQ, TQQQ], spy=True, price_rows=_FULL_HISTORY))
        risk = _get("/api/portfolio/risk").json()
        _override(_mock_session([QQQ, TQQQ], spy=True, price_rows=_FULL_HISTORY))
        explain = _get().json()
        ex = explain["explanation"]
        assert ex["source"] == "deterministic"
        assert {k: v for k, v in ex.items() if k != "source"} == risk["risk_grade_explanation"]

    def test_risk_endpoint_explanation_null_without_grade(self):
        # No grade -> inline explanation is null (dashboard shows nothing).
        _override(_mock_session([QQQ, TQQQ], price_rows=[]))
        risk = _get("/api/portfolio/risk").json()
        assert risk["risk_grade"] is None
        assert risk["risk_grade_explanation"] is None
