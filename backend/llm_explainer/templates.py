"""Deterministic, plain-English explanations of portfolio risk data.

Pure functions: structured risk-grade data in, human-readable strings out.
No I/O, no network, no randomness, no LLM. This is the always-on baseline
explainer — the project's core promise that a beginner can *learn* from the
risk grade, not just see a letter. PR2's LLM layer rephrases the same
structured data and falls back to these exact strings on any failure.

Design rule (non-negotiable): every *portfolio-specific* figure and ticker in
the output traces to the input payload. Those live only in the dynamic fields
(`headline`, `overview`, `detail`, and the numeric `penalty`/`score`), which
reuse the engine's per-component `reason` strings verbatim — so the text can
never claim a portfolio figure the risk engine didn't produce.

The static educational copy (`_COMPONENTS[*].meaning`) is trusted, fixed prose
and may contain *illustrative* numbers ("2x or 3x ETFs", "a beta above 1") that
describe the concept, not this portfolio. It is not subject to the traceability
guard. This scoping matters for PR2: the LLM validator must check the dynamic
fields the same way (see `tests/test_explainer_templates.py::_output_text`),
not the static copy — running number-traceability over an LLM-rephrased
`meaning` would wrongly reject those legitimate illustrative figures.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Static educational copy. Trusted, fixed prose. May contain illustrative
# numbers (e.g. "2x or 3x ETFs") that describe the concept, NOT this portfolio
# — portfolio-specific figures only ever come from the input payload.
# ---------------------------------------------------------------------------

# Human labels + a beginner-friendly "what this measures" for each component of
# the risk grade. Keyed by the component names risk_grade() emits.
_COMPONENTS: dict[str, dict[str, str]] = {
    "concentration": {
        "label": "Concentration",
        "meaning": (
            "Concentration measures how much of your money rides on a few "
            "holdings or a single sector. The more concentrated you are, the "
            "more a single bad move can hurt the whole portfolio."
        ),
    },
    "correlation": {
        "label": "Correlation",
        "meaning": (
            "Correlation measures how closely your holdings move together. "
            "When everything is highly correlated it tends to fall at the same "
            "time, so owning several of them gives you less real "
            "diversification than the number of holdings suggests."
        ),
    },
    "leverage": {
        "label": "Leverage",
        "meaning": (
            "Leverage measures how much your holdings amplify market moves. "
            "Leveraged funds (like 2x or 3x ETFs) magnify both gains and "
            "losses, and they tend to decay over time in choppy markets."
        ),
    },
    "beta": {
        "label": "Market sensitivity (beta)",
        "meaning": (
            "Beta measures how much your portfolio moves relative to the "
            "overall market. A beta above 1 means you swing more than the "
            "market does — in both directions."
        ),
    },
    "drawdown": {
        "label": "Historical drawdown",
        "meaning": (
            "Max drawdown is the worst peak-to-trough drop this portfolio "
            "would have suffered historically. It's a gut-check for how deep a "
            "decline you'd have had to sit through."
        ),
    },
}

# Component display order — most beginners think about concentration and
# leverage first, so lead with those; drawdown (the historical gut-check) last.
_ORDER = ["concentration", "leverage", "beta", "correlation", "drawdown"]

# Severity buckets by penalty as a fraction of the component's max penalty,
# with the plain-English contribution phrase for each. Ordered low → high;
# the first bucket whose ceiling the fraction is under wins.
_SEVERITY_BANDS: list[tuple[float, str, str]] = [
    (0.001, "none", "This isn't adding meaningful risk right now."),
    (0.20, "low", "This is a minor contributor to your risk."),
    (0.50, "moderate", "This is a moderate contributor to your risk."),
    (0.80, "high", "This is a major contributor to your risk."),
    (float("inf"), "severe", "This is one of the biggest risks in your portfolio."),
]

DISCLAIMER = (
    "This is an educational breakdown of your portfolio's risk measurements, "
    "not financial advice. Every figure comes from historical data and your "
    "current holdings."
)


def _severity(penalty: float, max_penalty: float) -> tuple[str, str]:
    """Classify a component penalty into a severity label + contribution phrase.

    The fraction penalty/max_penalty is a category, not a claimed figure, so it
    never appears verbatim in the output — only the label and phrase do.
    """
    frac = penalty / max_penalty if max_penalty else 0.0
    for ceiling, label, phrase in _SEVERITY_BANDS:
        if frac < ceiling:
            return label, phrase
    # Unreachable (last band is inf), but keep the type-checker + safety happy.
    return _SEVERITY_BANDS[-1][1], _SEVERITY_BANDS[-1][2]


def _capitalize(text: str) -> str:
    """Capitalize the first letter without touching the rest (unlike .capitalize)."""
    return text[:1].upper() + text[1:] if text else text


def explain_grade(grade: dict) -> dict:
    """Turn a `risk_grade` payload into a plain-English explanation payload.

    ``grade`` is the dict produced by ``risk.math.risk_grade`` (as serialized
    by the risk endpoints): ``{grade, score, components, interpretation}``,
    where each component is ``{penalty, max_penalty, reason}``.

    Returns a presentation-ready dict::

        {
          "grade": "B",
          "score": 72.0,
          "headline": "...",       # one-line summary
          "overview": "...",       # score + interpretation + top risk drivers
          "components": [          # one entry per gradable component, in _ORDER
            {"key", "label", "penalty", "max_penalty",
             "severity", "meaning", "detail"},
            ...
          ],
          "disclaimer": "...",
        }

    Pure and deterministic — same input, same strings, every time. All figures
    (``score``, per-component ``penalty``/``max_penalty``, and the numbers/
    tickers inside each ``reason``) come straight from ``grade``.
    """
    letter = grade["grade"]
    score = grade["score"]
    components_in = grade["components"]
    interpretation = grade["interpretation"]

    headline = f"Your portfolio scored {score} out of 100 — a risk grade of {letter}."

    sections: list[dict] = []
    for key in _ORDER:
        comp = components_in.get(key)
        if comp is None:
            continue
        penalty = comp["penalty"]
        max_penalty = comp["max_penalty"]
        severity, phrase = _severity(penalty, max_penalty)
        meta = _COMPONENTS[key]
        # The reason carries the figures (and tickers, for correlation); reuse
        # it verbatim so nothing is re-formatted (or fabricated), then append
        # the severity framing.
        detail = f"{_capitalize(comp['reason'])}. {phrase}"
        sections.append(
            {
                "key": key,
                "label": meta["label"],
                "penalty": penalty,
                "max_penalty": max_penalty,
                "severity": severity,
                "meaning": meta["meaning"],
                "detail": detail,
            }
        )

    # Top risk drivers: components carrying the most penalty. Names it plainly
    # so a beginner knows where to focus. No figures — just labels.
    scored = sorted(
        (s for s in sections if s["penalty"] > 0),
        key=lambda s: s["penalty"],
        reverse=True,
    )
    if not scored:
        drivers = "Nothing stands out as a major risk right now."
    else:
        top = [s["label"].lower() for s in scored[:2]]
        if len(top) == 1:
            drivers = f"The main thing driving your risk is {top[0]}."
        else:
            drivers = f"The biggest contributors to your risk are {top[0]} and {top[1]}."

    overview = f"{_capitalize(interpretation)}. {drivers}"

    return {
        "grade": letter,
        "score": score,
        "headline": headline,
        "overview": overview,
        "components": sections,
        "disclaimer": DISCLAIMER,
    }
