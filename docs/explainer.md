# M8 — Explainer Layer

Turns the *what* (signals, grades, risk numbers already computed) into a plain-English
*why* a beginner can learn from. This is the project's core promise — "transparent about
why it gave me that rating so I can learn and improve." Last V0-core milestone before
M9 (pipeline) and M10 (polish).

## Non-negotiables

- **Not a chatbot.** No free-text input, no chat box. The LLM only rephrases structured
  data the backend already computed. (See `features.md` Defer list + this milestone.)
- **The LLM never computes.** Every number and ticker in the output must trace to the
  structured input; otherwise it's rejected.
- **The app never gates on the LLM.** Deterministic templates are the always-on baseline;
  the LLM enriches. Remove the API key → the app still fully works.
- **Backend owns explanation *content*; frontend owns *presentation*.** New prose
  explanations live in `backend/llm_explainer/`; the frontend renders what the API returns. This
  keeps the LLM's context and the UI reading from a single source. (The existing M5.6
  `SignalBreakdown` per-indicator bar UI is a different, more granular surface and stays
  as-is.)

## v1 scope

- **Risk grade only.** Explain the portfolio risk grade + its penalties (concentration,
  correlation, leverage, beta, drawdown) in plain English. One payload, highest value,
  proves the pattern end-to-end. Per-holding signal and per-indicator explanations are a
  later increment.

## Sequencing

### PR1 — Deterministic explainer (backend, no API dependency)

The required fallback, built first. Low risk; much of the raw material already exists
(`risk_grade` penalty reasons, `composite.py` contributions/directions).

- `backend/llm_explainer/templates.py` — pure functions: structured risk data → plain-English
  strings. Deterministic, tested, no I/O. Reuses `risk_grade` reasons as inputs.
- Endpoint: `GET /api/portfolio/risk/explain` (auth-gated like the rest of
  `/api/portfolio/*`), returning the deterministic explanation payload.
- Frontend: an "Explain" surface on the risk grade card that renders the returned text,
  education-framed, wrapped with a not-financial-advice disclaimer.

Ships value on its own and is the fallback PR2 depends on.

### PR2 — Structured LLM enrichment (on top of PR1)

- `backend/llm_explainer/client.py` — thin `anthropic` SDK wrapper. Model `claude-opus-4-8`,
  adaptive thinking, `messages.parse()` against a schema (SDK-layer output validation).
  Handles `stop_reason == "refusal"`, timeouts, retries.
- `backend/llm_explainer/context.py` — assembles the *structured* risk data (grade, penalties,
  weights, contributions) into the prompt. The user never types into this.
- `backend/llm_explainer/prompts/` — versioned prompt templates (`v1/…`), one per analysis type.
- `backend/llm_explainer/validator.py` — reject hallucinated tickers/numbers: every ticker and
  figure in the output must appear in the structured input, else discard and fall back to
  PR1's deterministic text.
- `backend/llm_explainer/cache.py` + migration `llm_analysis_cache` — key on
  `(prompt_version, data_hash)`; no redundant API calls; invalidates when underlying data
  changes.
- Fallback wiring: any failure (no key, refusal, validation reject, timeout) → serve PR1
  deterministic text, seamlessly.

## Deferred out of M8

- LLM chat / free-text Q&A — out of scope, permanently.
- Persisting explanations beyond the cache — M9 territory.

## Config

- `ANTHROPIC_API_KEY` → `.env` / `.env.example` and Docker build/runtime (needed only at
  PR2; PR1 needs nothing). Key deployed to oc40 when PR2 ships.
