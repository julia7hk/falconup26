"""Assemble the structured risk explanation into prompt input (M8 PR2).

This is the experimentation seam: it decides *what* the model gets to see and
rephrase. Change what context the LLM works from — add a component field, feed
it the raw grade, trim the facts — here, without touching the API wiring
(``client.py``) or the prompt wording (``prompt.py``).

Pure and I/O-free. The input is the deterministic PR1 explanation
(``templates.explain_grade``); the output is the user-turn message content. It
deliberately feeds the model *only* the already-computed explanation — never
any user free-text — so there is no channel for prompt injection or for the
model to be asked to compute anything new.
"""

from __future__ import annotations

import json


def build_user_content(explanation: dict) -> str:
    """Turn the deterministic explanation into the model's user-turn content.

    ``explanation`` is the dict from ``templates.explain_grade``. We hand the
    model a compact JSON block of exactly the fields it may rephrase — the
    grade/score for context, the dynamic ``headline``/``overview``, and each
    component's ``label``/``meaning``/``detail`` — plus a one-line instruction.

    The engine's ``detail`` strings are the only place figures and tickers live,
    so those are the facts the model must preserve verbatim; ``meaning`` is the
    static educational copy it can lean on for tone. Nothing here is
    user-authored.
    """
    facts = {
        "grade": explanation["grade"],
        "score": explanation["score"],
        "headline": explanation["headline"],
        "overview": explanation["overview"],
        "components": [
            {
                "key": c["key"],
                "label": c["label"],
                "meaning": c["meaning"],
                "detail": c["detail"],
            }
            for c in explanation["components"]
        ],
    }
    return (
        "Here are the risk facts to rephrase. Rephrase `headline`, `overview`, "
        "and each component's `detail` into warmer, beginner-friendly prose, "
        "following every rule above. Preserve every number and ticker exactly as "
        "written; do not introduce new ones.\n\n"
        f"{json.dumps(facts, indent=2)}"
    )
