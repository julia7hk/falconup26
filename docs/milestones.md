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

- [ ] `SortinoResult` model in `models.py` (value, risk_free_rate, interpretation)
- [ ] `sortino_ratio()` in `math.py` — same signature as `sharpe_ratio()`, filter for negative returns in denominator
- [ ] `MaxDrawdownResult` model in `models.py` (value as %, peak_date, trough_date)
- [ ] `max_drawdown()` in `math.py` — running max vs current value over closes
- [ ] Add normalization cases in `composite.py` for both new indicators
- [ ] Rebalance composite weights (9 indicators instead of 7)
- [ ] Tests for Sortino + max drawdown in `test_indicators.py`
- [ ] Wire into `/api/symbols/{ticker}/indicators` endpoint
- [ ] Frontend: add Sortino + max drawdown cards to indicator panel

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

## Milestone 5.5: Production Deploy

- [x] Deployed to oc40 (`falconup.julia7hk.com`) — Oracle Cloud free tier Ampere ARM64
- [x] Postgres 16 + Redis on host (not in Docker)
- [x] Nginx reverse proxy in Docker
- [x] Cloudflare edge TLS (SSL mode: Full)
- [x] CI/CD: GitHub Actions → GHCR → pull on oc40

## Milestone 5.6: Authentication & Multi-Tenancy

> **Status: NOT STARTED**
>
> The app is publicly deployed with zero authentication. Anyone who visits
> `falconup.julia7hk.com` can view, add, edit, and delete portfolio holdings.
> There is a single shared `portfolio_holding` table with no `user_id` —
> everyone shares one portfolio.
>
> **Why this is the next priority:**
>
> 1. **Resume value** — auth touches every layer of the stack (DB migrations,
>    backend middleware, API design, frontend state, cookies, security). It's
>    one of the most asked-about topics in interviews, and building it from
>    scratch (not just plugging in a library) demonstrates real understanding.
> 2. **Security** — the app is live and anyone can modify portfolio data.
> 3. **Multi-user foundation** — retrofitting `user_id` later is painful
>    (migration on existing data, every query needs scoping, upsert logic
>    changes). Doing it now means multi-user support is a natural extension,
>    not a rewrite.
> 4. **Project goals alignment** — primary goal is learning/resume, secondary
>    is personal use, tertiary is multi-user/monetization. Auth serves all
>    four at once.

### Database

- [ ] Alembic migration (hand-authored raw SQL, per project convention):
  - `user` table: `id` (serial PK), `email` (unique, NOT NULL), `password_hash` (NOT NULL), `name`, `created_at` (default now()), `updated_at` (default now())
  - Add `user_id` (NOT NULL FK → `user.id`) to `portfolio_holding`
  - Drop existing UNIQUE on `portfolio_holding.symbol_id`
  - Add UNIQUE on `(user_id, symbol_id)` — one holding per symbol *per user*

### Backend (FastAPI)

- [ ] Auth dependencies + utilities:
  - Password hashing with bcrypt (`passlib[bcrypt]` or `bcrypt`)
  - JWT creation + validation (PyJWT, HS256, short-lived access token)
  - `get_current_user` dependency — extract + validate JWT from httpOnly cookie, return user row
  - `JWT_SECRET` env var in `.env` / `.env.example`
- [ ] Auth endpoints:
  - `POST /api/auth/register` — validate email/password, hash password, insert user, return JWT in httpOnly cookie
  - `POST /api/auth/login` — verify credentials, return JWT in httpOnly cookie
  - `POST /api/auth/logout` — clear the httpOnly cookie
  - `GET /api/auth/me` — return current user info (for frontend session check on page load)
- [ ] Protect portfolio routes:
  - All `/api/portfolio/*` routes get `Depends(get_current_user)`
  - Every `portfolio_holding` query scoped by `user_id` (SELECT, INSERT, UPDATE, DELETE)
  - Upsert conflict target changes from `(symbol_id)` to `(user_id, symbol_id)`

### Frontend (Next.js)

- [ ] Auth pages:
  - `/login` page (email + password form)
  - `/register` page (email + password + name form)
- [ ] Auth state:
  - Check `GET /api/auth/me` on app load to determine login state
  - Redirect unauthenticated users to `/login`
  - All `fetch` calls use `credentials: 'include'` for httpOnly cookie
- [ ] Auth UI:
  - Logout button in header (visible when logged in)
  - User email/name display in header
  - Protected route wrapper component

### Security Decisions (and why — interview talking points)

- **httpOnly cookies** over localStorage — XSS can't read the token via `document.cookie`. This is a deliberate, defensible choice.
- **bcrypt** for password hashing — intentionally slow, resistant to brute force. Not MD5/SHA256.
- **Short-lived JWT** — limits exposure window if a token leaks. Consider refresh token pattern for UX.
- **Server-side validation on every request** — never trust the client. `get_current_user` runs on every protected route.
- **SameSite=Lax + Secure** cookie flags — CSRF protection without a separate token.

### Testing

- [ ] pytest: register, login, logout, me endpoints (happy path + validation errors)
- [ ] pytest: portfolio CRUD returns 401 without auth
- [ ] pytest: user A cannot see/modify user B's holdings
- [ ] Manual E2E: register → add holdings → logout → register as different user → see empty portfolio

## Milestone 6: Portfolio Risk Engine

Depends on M5 (needs holdings to analyze).

- [ ] Concentration score — Herfindahl index across holdings + sector exposure breakdown
- [ ] Pairwise correlation matrix of all holdings (rolling 1-year daily returns)
- [ ] Effective leverage — weighted average leverage factor across portfolio
- [ ] Portfolio beta — weighted beta vs S&P 500
- [ ] Max drawdown estimate — historical volatility x effective leverage
- [ ] Stress scenarios — model portfolio impact for predefined shocks (Nasdaq -10%, rates +1%, semiconductor crash)
- [ ] Overall portfolio risk grade (A–F) from composite of above metrics
- [ ] API endpoints: `GET /api/portfolio/risk`, `GET /api/portfolio/correlation`, `GET /api/portfolio/stress?scenario=...`
- [ ] Frontend: risk grade card, concentration pie chart, correlation heatmap, effective leverage gauge, stress scenario cards

## Milestone 7: What-If Analysis

- [ ] `POST /api/portfolio/what-if` — accepts symbol + quantity, returns before/after risk metrics diff
- [ ] Frontend: structured form (pick symbol + quantity), before/after comparison, visual diff of which metrics improved/worsened

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
