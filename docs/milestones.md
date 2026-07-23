# FalconUp Milestones — MVP

> **V0 core**: portfolio dashboard + per-symbol indicators + portfolio-level
> risk analysis (concentration, correlation, leverage, stress tests) +
> structured LLM explainer layer. Post-MVP items in [features.md](features.md)
> (V0.5–V2).

## Milestone 1: Project Foundation

- [x] `.env`, `.envrc`, `.env.example` — environment variable setup (direnv)
- [x] `uv` as Python package manager (`pyproject.toml`, lockfile)
- [x] Alembic init in `backend/` — database migration management
- [x] FastAPI in `backend/` — Python 3.13
- [x] Next.js (App Router) in `frontend/` — TypeScript + Tailwind, mobile-first
- [x] Docker + Compose in `ops/`
- [x] Github Actions CI/CD pipeline
- [x] Nginx + Domain wiring

## Milestone 2: Data Source Integration

- [x] Evaluate market data APIs (Yahoo Finance, Alpha Vantage, Twelve Data, Polygon, Finnhub)
- [x] Select primary + fallback data source — yfinance (primary), abstraction layer (`DataProvider` protocol) allows one-line swap
- [x] Price fetcher — current price, historical OHLCV (daily)
- [x] Rate limiting + caching layer — TTL cache (quotes 1 min, history 1 hr, search 24 hr)
- [x] FRED integration for macro data (VIX, yield curves, fed funds rate) — `/api/macro/*` endpoints, 1hr cache
- [x] Sector/industry data per symbol (for concentration analysis) — ETF category map + yfinance fallback, `/api/symbols/{ticker}/sector`

## Milestone 3: Database Schema

- [x] Migration: `symbol` table (ticker, name, type: ETF/stock, sector, industry, leverage_factor)
- [x] Migration: `portfolio_holding` table (symbol, shares, avg_cost)
- [x] Migration: `price_history` table (symbol, date, OHLCV)
- [x] Migration: `macro_history` table (series: fed_funds/vix/treasury_2y/treasury_10y, date, value)
- [x] SQLAlchemy engine + async session
- [x] Seed default symbols (QQQ, TQQQ, SOXL + 13 more) with leverage factors + sector data
- [x] One-time backfill script — pull historical OHLCV + FRED data into Postgres

## Milestone 4: Per-Symbol Indicator Engine

- [x] Result models — `backend/indicators/models.py` (RSIResult, MACDResult, BollingerResult, SMACrossoverResult, ATRResult, BetaResult, SharpeResult, CompositeResult)
- [x] Indicator math — `backend/indicators/math.py` (rsi, macd, bollinger_width, sma_crossover, atr, beta, sharpe_ratio + _ema, _sma helpers)
- [x] Composite scoring — `backend/indicators/composite.py` (normalize_signal, composite_score, weighted Buy/Hold/Sell classification)
- [x] Math tests — `backend/tests/test_indicators.py` (34 tests, deterministic data)
- [x] API endpoint — `GET /api/symbols/{ticker}/indicators` with SPY join for beta, macro_history for Sharpe risk-free rate
- [x] API tests — `backend/tests/test_api_indicators.py` (mock DB, response shape, 404)
- [x] Wire up — numpy dep, router registered in main.py, 70 tests passing
- [x] Frontend indicators panel — composite signal banner + 7 indicator cards, loads on symbol select

### Rework composite scoring

- [x] Replace discrete buckets with smooth linear interpolation (Bollinger, ATR, Beta)
- [x] Fix MACD normalization — use max(signal_line, macd_line) with 1.5x multiplier
- [x] Slow SMA crossover decay — full strength for 30 days, floor at 0.3, fades over 200 days
- [x] Add SMA gap signal when no crossover detected (weak directional signal from SMA-50 vs SMA-200 gap)
- [x] Lower buy/sell thresholds from ±0.25 to ±0.15
- [x] Rebalance confidence formula — agreement 0.6, score magnitude 0.4
- [x] Tests updated — 8 new normalization tests (42 indicator tests, 78 total)

### Add Sortino ratio + max drawdown to indicator engine

Sortino penalizes only downside volatility (better than Sharpe for conservative investors).
Max drawdown shows worst peak-to-trough loss — critical for leveraged ETFs like TQQQ/SOXL.

- [x] `SortinoResult` model in `models.py` (value, risk_free_rate, interpretation)
- [x] `sortino_ratio()` in `math.py` — same signature as `sharpe_ratio()`, downside-deviation denominator (target semi-deviation, MAR = risk-free rate)
- [x] `MaxDrawdownResult` model in `models.py` (value as %, peak_date, trough_date)
- [x] `max_drawdown()` in `math.py` — running max vs current value over closes (takes closes + dates)
- [x] Add normalization cases in `composite.py` for both new indicators
- [x] Rebalance composite weights (9 indicators instead of 7)
- [x] Tests for Sortino + max drawdown in `test_indicators.py`
- [x] Wire into `/api/symbols/{ticker}/indicators` endpoint
- [x] Frontend: add Sortino + max drawdown cards to indicator panel

## Milestone 5: Portfolio

DB table exists (`portfolio_holding` from M3). This milestone adds the API + frontend to manage holdings.

### Backend — `backend/routers/portfolio.py`

- [x] `POST /api/portfolio/holdings` — add holding (symbol ticker + shares + avg cost). Look up symbol_id, 404 if not in DB
- [x] `GET /api/portfolio` — all holdings with current price, market value, P&L per position, total portfolio value
- [x] `PUT /api/portfolio/holdings/{id}` — update shares or avg cost
- [x] `DELETE /api/portfolio/holdings/{id}` — remove holding

### Frontend — holdings UI

- [x] Add holding form — symbol picker (from catalog or search) + shares + avg cost
- [x] Holdings list — ticker, shares, avg cost, current price, market value, P&L, gain/loss %
- [x] Portfolio summary bar — total value, total P&L, day change
- [x] Buy/Hold/Sell badge per holding (from existing indicators endpoint)
- [x] Empty state + onboarding — prompt to add first holding, suggest QQQ/TQQQ/SOXL as examples

## Milestone 5.5: Authentication & Multi-Tenancy

Better Auth + FastAPI session bridge. See [auth.md](auth.md) for architecture and conceptual background.

### 1. Database

- [x] Alembic migration: Better Auth tables (`"user"`, `session`, `account`, `verification` — camelCase columns)
- [x] Alembic migration: truncate `portfolio_holding` (existing data is test), add `user_id` (text, NOT NULL, FK → `"user".id`), drop UNIQUE on `symbol_id`, add UNIQUE on `(user_id, symbol_id)`

### 2. Frontend — Prisma

- [x] `npx prisma init` — initialize Prisma in `frontend/`
- [x] Add `DATABASE_URL` to `frontend/.env` (localhost for dev, Docker bridge IP for containers — same pitfall as backend)
- [x] `npx prisma db pull` — introspect Postgres schema into `prisma/schema.prisma`
- [x] `npx prisma generate` — generate typed Prisma client
- [x] Prisma client singleton (`lib/db.ts`)

### 3. Frontend — Better Auth

- [x] `npm install better-auth`
- [x] Auth server config (`lib/auth.ts`) — Prisma adapter, email/password
- [x] Auth client (`lib/auth-client.ts`) — `createAuthClient()`
- [x] Catchall route (`/api/auth/[...all]/route.ts`)
- [x] `BETTER_AUTH_SECRET` env var (add to `.env`, `.env.example`, Docker build args)
- [x] `/sign-in` page
- [x] `/sign-up` page
- [x] `authClient.useSession()` hook for session state
- [x] Main page public — portfolio section only visible when signed in; sign-in link in header when logged out
- [x] Header: user name (links to /profile) + sign-out button (logged in) / sign-in link (logged out)
- [x] `/profile` page — portfolio summary, change name, change password

### 4. Backend (FastAPI) — session bridge

- [x] `get_current_user` dependency — read `better-auth.session_token` cookie, look up session in DB, resolve user
- [x] All `/api/portfolio/*` routes get `Depends(get_current_user)` (`/api/symbols/*` and `/api/macro/*` stay public)
- [x] All `portfolio_holding` queries scoped by `user_id`
- [x] Upsert conflict target: `(symbol_id)` → `(user_id, symbol_id)`

### 5. Testing

- [x] pytest: portfolio CRUD returns 401 without session cookie
- [x] pytest: user A cannot see/modify user B's holdings
- [x] Manual E2E: register → add holdings → sign out → register new user → see empty portfolio

## Milestone 5.6: Mobile Layout + Polish

- [x] Fix mobile layout — responsive padding, stacking grids, holdings cards, price history, symbol lookup
- [x] Per-holding signal dropdown — expand Buy/Hold/Sell badge to show why, personalized to the user's position (avg cost, position size, portfolio context). Precursor to M8 explainer. Shared `SignalBreakdown` component (symbol-level "why" + per-indicator contribution bars) reused by the symbol-detail card and the holding dropdown; `HoldingSignalPanel` adds deterministic position framing (P&L, portfolio weight, concentration nudge) with an explicit "signal ignores your entry price, not financial advice" guardrail.

## Milestone 6: Portfolio Risk Engine

Depends on M5 (needs holdings to analyze).

- [x] Concentration score — Herfindahl index across holdings + sector exposure breakdown
- [x] Pairwise correlation matrix of all holdings (rolling 1-year daily returns)
- [x] Effective leverage — weighted average leverage factor across portfolio
- [x] Portfolio beta — weighted beta vs S&P 500
- [x] Max drawdown — actual historical max drawdown from portfolio value time series (peak-to-trough), not an estimate
- [x] Historical stress scenarios — replay real market events (COVID crash, 2022 tech selloff, 2018 Q4, 2020 recovery, worst-30-days) using actual price data from `price_history`, per-holding breakdown with real returns
- [x] Transparent risk grade (A–F) — each component (concentration, correlation, leverage, beta, drawdown) has a visible penalty score with plain-English reason, so the user sees exactly why they got the grade
- [x] API endpoints: `GET /api/portfolio/risk`, `GET /api/portfolio/correlation`, `GET /api/portfolio/stress?scenario=...`
- [x] Frontend: risk grade card (expandable breakdown), concentration pie chart, correlation heatmap, effective leverage gauge, stress scenario cards (with real historical returns + disclaimer)

## Milestone 7: What-If Analysis

Depends on M6. Simulate a hypothetical trade (buy or sell) and show the before/after risk-metric diff.
**No new math** — reuses the M6 risk engine by re-running it against a modified holdings list.

### Backend — refactor to make the risk engine reusable

- [x] Extract the compute-from-data logic in `get_portfolio_risk` (`routers/risk.py`) into a helper `_compute_risk_metrics(data) -> dict` (concentration, leverage, beta renorm, correlation guard, drawdown, grade). Both `GET /risk` and `POST /what-if` call it, so the two can never diverge.
- [x] Split the monolithic fetch into `_fetch_market_data` (DB holdings + live quotes + price history, with an **optional `extra_tickers`** arg so a buy of an unheld symbol loads its history/quote) and `_build_risk_data` (pure derivation of weights/returns/betas/portfolio series from *any* holdings list). `_fetch_portfolio_risk_data` stays as a thin wrapper so `/risk`, `/correlation`, `/stress` are unchanged. What-if runs `_build_risk_data` twice (before + after).

### Backend — what-if endpoint

- [x] `POST /api/portfolio/what-if` — auth-gated. Body: `{ ticker, action: "buy" | "sell", quantity }`. Returns `{ trade, before, after, diff }` where before/after are the full `_compute_risk_metrics` payloads.
- [x] Apply the trade to a copied holdings list: buy → `shares + qty` (append a new row priced at the live quote / last close if not held); sell → `shares - qty` (drop the row at 0). Recompute weights by market value from the modified shares.
- [x] Validation + edge cases: 404 if ticker not in `symbol` table; 400 on oversell / selling a symbol not owned; sell-to-zero removes the holding; degrade gracefully when the result leaves <2 holdings (correlation needs ≥2) or <60 days of history (drawdown/grade unavailable) — mirror the `None` handling already in `/risk`.
- [x] `diff` block: per-metric before/after + delta + a direction flag (improved / worsened / unchanged / **unavailable**). Grade-direction convention: lower concentration/leverage/beta/drawdown = improved; higher grade score = improved. Risk-grade entry also carries `before_grade`/`after_grade` letters.

### Backend — tests (`tests/test_api_whatif.py`, 12 tests)

- [x] 401 without session cookie; 422 on bad quantity/action
- [x] Buy more of a held symbol → weights shift, leverage recomputes
- [x] Buy a symbol not currently held → appended, holdings_count reflects it
- [x] Sell partial / sell-to-zero (holding removed) / oversell rejected / sell-not-owned rejected
- [x] Empty portfolio + buy = single-holding portfolio (graceful); diff payload shape

### Frontend — what-if UI

- [x] Types: `WhatIfRequest`, `WhatIfDiffEntry`, `WhatIfResponse` (before/after/diff) in `types.ts`
- [x] Collapsible `WhatIfPanel` in the Risk Analysis section: symbol field (owned tickers offered via `<datalist>`, but any symbol accepted) + buy/sell toggle + quantity.
- [x] Before/after comparison — reuse `RiskGradeCard` for each side; "grade unavailable" fallback when history is insufficient.
- [x] Visual diff — per-metric before→after table with arrow + green(improved)/red(worsened)/neutral, driven by the backend's `direction` flag (no client-side risk logic).
- [x] Framing: labeled a simulation ("nothing is saved"), backend not-advice disclaimer, never modifies the real portfolio.

## Milestone 8: Explainer Layer

### Deterministic Explainers (always available, no API dependency)

- [ ] Per-indicator plain-English templates ("RSI is 28 — below 30 indicates oversold, which is a bullish signal")
- [ ] Overall signal rationale ("3 of 7 indicators are bullish, 2 bearish, 2 neutral → Hold with low confidence")
- [ ] Portfolio risk templates — concentration, leverage, correlation summaries as formatted strings

### Structured LLM Explainer (enriches deterministic layer)

Architecture: LLM never computes anything. It translates structured risk data
into personalized, contextual explanations. No chat box, no free-text input.

- [ ] Prompt template module (`backend/llm/prompts/`) — versioned, tested prompt templates per analysis type
- [ ] Context assembler (`backend/llm/context.py`) — takes typed risk data, formats into structured prompt context
- [ ] Output validator (`backend/llm/validator.py`) — reject hallucinated tickers, enforce output structure
- [ ] Deterministic fallback — if LLM unavailable or validation fails, serve template-string explanations (app never gates on LLM)
- [ ] Response cache (`backend/llm/cache.py`) — keyed on (prompt_version, data_hash), no redundant API calls
- [ ] API client (`backend/llm/client.py`) — thin wrapper with retry, timeout, rate limiting
- [ ] Migration: `llm_analysis_cache` table
- [ ] Education framing — all outputs wrapped with disclaimer, framed as education not financial advice
- [ ] Frontend: "Explain" button on risk metrics and indicator cards

## Milestone 9: Data Pipeline

- [ ] Scheduled price refresh (daily OHLCV backfill + intraday current price)
- [ ] Indicator recalculation on new price data
- [ ] Portfolio risk recalculation on new indicator data
- [ ] Migration: `indicator_snapshot` table — persist computed indicators on schedule
- [ ] LLM cache invalidation when underlying data changes
- [ ] Stale-data detection + user-facing "last updated" timestamp

## Milestone 10: Polish & Launch

- [ ] Loading skeletons for price/indicator fetches
- [ ] Error states (API down, invalid symbol, rate limit hit)
- [ ] LLM fallback UX — seamless degradation to deterministic explainers
- [ ] Mobile-first responsive layout audit
- [ ] Dark mode
- [ ] PWA manifest + "Add to home screen"
- [ ] Open Graph / Twitter Card tags
- [ ] robots.txt + sitemap
- [ ] Lighthouse audit (perf, a11y, best practices)

## Milestone 11: Recommendation / Action Layer

Design + open questions: [recommendations.md](recommendations.md). Builds on M6
(risk engine), M7 (what-if = the ranking primitive), M8 (explainer). Ships
PR1 (deterministic) then PR2 (LLM rephrases the ranked suggestions).

### PR1 — Deterministic recommender (no API dependency)

- [ ] Candidate generation: search the seeded `symbol` catalog — each symbol as a hypothetical contribution-sized buy.
- [ ] Score each candidate via the what-if engine (Δ risk-grade score); rank by improvement per dollar. Buy-only (no taxable event, no per-lot tracking needed).
- [ ] Map the ranked buys back to the flagged risk component for a plain-English "why" (reuse M8 template pattern).
- [ ] Endpoint `GET /api/portfolio/risk/recommendations` — auth-gated; optional `contribution` amount; returns top-N ranked, each with its simulated before/after.
- [ ] Tests: deterministic ranking, candidates only from catalog, buy-only, framing (educational scenario, not directive).
- [ ] Frontend: "Ways to improve" surface under the risk grade — ranked suggestions with simulated Δgrade + prominent not-financial-advice disclaimer.

### PR2 — LLM enrichment (on top of PR1)

- [ ] LLM rephrases the ranked, already-simulated suggestions; validator rejects any ticker/number not in the structured input; falls back to PR1.

### Deferred (later increments)

- [ ] Sell-side recommendations + per-lot tax awareness (needs purchase-date / `lot` schema; short-term vs long-term capital-gains warning).
- [ ] Contribution cadence persistence (amount + frequency) rather than a one-off amount.
- [ ] Account-type awareness (taxable vs Roth/IRA) — ties into V2 multi-portfolio.

## Backlog (separate PRs)

- [ ] Replace raw SQL `text()` queries with SQLAlchemy ORM models (sqlacodegen → generated models). Currently the entire backend uses `text()` consistently; this is a codebase-wide refactor, not tied to any feature milestone.
- [ ] Better Auth admin plugin — role-based access control, user management, ban/unban (https://better-auth.com/docs/plugins/admin). Already used in kkulgag.
- [ ] Google OAuth sign-in — Better Auth supports OAuth providers. Email + Google can coexist on the same email (account linking). Requires Google Cloud Console OAuth app setup.
- [ ] Automatic stress scenario detection. The stress scenarios were extracted from `risk/math.py` into `backend/risk/stress_scenarios.json` (data out of the pure-math module) — but the dates are still hand-researched. Goal: detect major market drawdowns automatically from `price_history` (e.g. scan SPY for the worst peak-to-trough windows over a lookback, or threshold-based drawdown episodes) so the scenario list stays accurate without manual date-picking. Keep the curated, named events (e.g. "COVID Crash") for pedagogical value — beginners learn more from recognizable events than "worst 74-day window" — so this augments/generates the JSON rather than replacing curation with raw math. Storage (JSON vs a `stress_scenario` DB table) is deferred until this is built; either is fine.
