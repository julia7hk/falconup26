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
- [ ] Sector/industry data per symbol (for concentration analysis)

## Milestone 3: Database Schema

- [ ] Migration: `symbol` table (ticker, name, type: ETF/stock, sector, industry, leverage_factor)
- [ ] Migration: `portfolio_holding` table (symbol, shares, avg_cost)
- [ ] Migration: `price_history` table (symbol, date, OHLCV)
- [ ] Migration: `indicator_snapshot` table (symbol, date, indicator values)
- [ ] Migration: `portfolio_risk_snapshot` table (concentration score, effective leverage, portfolio beta, max drawdown estimate, correlation matrix blob, risk grade, computed_at)
- [ ] Migration: `llm_analysis_cache` table (prompt_version, data_hash, response, created_at, ttl)
- [ ] SQLAlchemy engine + async session
- [ ] Seed default symbols (QQQ, TQQQ, SOXL) with leverage factors + sector data

## Milestone 4a: Per-Symbol Indicator Engine

- [ ] RSI (14-day)
- [ ] MACD (12/26/9)
- [ ] Bollinger Band width (20-day, 2 sigma)
- [ ] 50/200-day SMA crossover (golden cross / death cross)
- [ ] ATR (14-day volatility)
- [ ] Beta (vs S&P 500, 1-year)
- [ ] Sharpe ratio (1-year, risk-free rate from FRED)
- [ ] Composite signal score — weighted aggregate of all indicators
- [ ] Buy / Hold / Sell classification from composite score + confidence level

## Milestone 4b: Portfolio Risk Engine

- [ ] Concentration score — Herfindahl index across holdings + sector exposure breakdown
- [ ] Pairwise correlation matrix of all holdings (rolling 1-year daily returns)
- [ ] Effective leverage — weighted average leverage factor across portfolio
- [ ] Portfolio beta — weighted beta vs S&P 500
- [ ] Max drawdown estimate — historical volatility x effective leverage
- [ ] Stress scenarios — model portfolio impact for predefined shocks (Nasdaq -10%, rates +1%, semiconductor crash)
- [ ] Overall portfolio risk grade (A–F) from composite of above metrics
- [ ] What-if engine — recompute all portfolio risk metrics with a hypothetical position added/removed, return structured diff

## Milestone 5: Explainer Layer

### 5a: Deterministic Explainers (always available, no API dependency)

- [ ] Per-indicator status: current value, threshold that triggered, bullish/bearish/neutral
- [ ] Plain-English template per indicator ("RSI is 28 — below 30 indicates oversold, which is a bullish signal")
- [ ] Overall signal rationale ("3 of 7 indicators are bullish, 2 bearish, 2 neutral -> Hold with low confidence")
- [ ] Indicator weight transparency — show how much each indicator contributed to the composite
- [ ] Portfolio risk templates — concentration, leverage, correlation summaries as formatted strings

### 5b: Structured LLM Explainer (enriches deterministic layer)

Architecture: LLM never computes anything. It translates structured risk data
into personalized, contextual explanations. No chat box, no free-text input.

- [ ] Prompt template module (`backend/llm/prompts/`) — versioned, tested prompt templates per analysis type:
  - `concentration.py` — explain concentration risk given sector breakdown + Herfindahl score
  - `stress_test.py` — narrate stress scenario results
  - `portfolio_summary.py` — overall portfolio risk narrative
  - `what_if.py` — explain before/after diff when user models a hypothetical trade
- [ ] Context assembler (`backend/llm/context.py`) — takes typed risk data from the engine, formats into structured prompt context
- [ ] Output validator (`backend/llm/validator.py`) — reject responses that reference symbols not in portfolio, enforce output structure, catch hallucinations
- [ ] Deterministic fallback — if LLM is unavailable or validation fails, serve template-string explanations from 5a (app never gates on LLM)
- [ ] Response cache (`backend/llm/cache.py`) — keyed on (prompt_version, data_hash). Same portfolio state = same explanation. No redundant API calls.
- [ ] API client (`backend/llm/client.py`) — thin wrapper with retry, timeout, rate limiting
- [ ] Education framing — all LLM outputs wrapped with disclaimer, framed as education not financial advice

User-facing behavior: each risk metric on the dashboard has an "Explain"
button. Click triggers a structured prompt with the precomputed data. No user
prompt authoring.

## Milestone 6: Portfolio Dashboard — Frontend

### Tab 1: Holdings

- [ ] Add holding form (symbol lookup + shares + avg cost)
- [ ] Holdings list — current price, market value, P&L per position, gain/loss %
- [ ] Portfolio summary — total value, total P&L, day change
- [ ] Risk indicator panel per symbol — all 7 indicators in a compact card
- [ ] Buy/Hold/Sell badge per symbol with confidence score
- [ ] Deterministic signal explainer expandable per symbol
- [ ] "Explain" button per symbol — triggers LLM-generated contextual analysis

### Tab 2: Portfolio Risk

- [ ] Overall risk grade (A–F) with breakdown of contributing factors
- [ ] Concentration pie chart — sector exposure
- [ ] Correlation heatmap — pairwise holding correlations
- [ ] Effective leverage gauge
- [ ] Stress scenario cards — "if Nasdaq drops 10%, your portfolio drops ~X%"
- [ ] "Explain" button per risk metric — LLM-generated contextual paragraph

### Tab 3: What-If Analysis

- [ ] Structured form: pick symbol + quantity (no free text)
- [ ] Before/after comparison of all portfolio risk metrics
- [ ] Visual diff — which metrics improved, which worsened
- [ ] LLM-generated explanation of the impact

### General

- [ ] Mobile-first responsive layout — usable on phone during market hours
- [ ] Empty state + onboarding (seed QQQ, TQQQ, SOXL as defaults)

## Milestone 7: API Layer

- [ ] `GET /api/symbols/search?q=` — symbol lookup (autocomplete)
- [ ] `GET /api/symbols/{ticker}/price` — current + historical price
- [ ] `GET /api/symbols/{ticker}/indicators` — all indicator values + signal
- [ ] `POST /api/portfolio/holdings` — add holding
- [ ] `PUT /api/portfolio/holdings/{id}` — update holding
- [ ] `DELETE /api/portfolio/holdings/{id}` — remove holding
- [ ] `GET /api/portfolio` — full portfolio with indicators + signals for all holdings
- [ ] `GET /api/portfolio/risk` — portfolio-level risk metrics (concentration, leverage, beta, correlation, risk grade)
- [ ] `GET /api/portfolio/correlation` — correlation matrix
- [ ] `GET /api/portfolio/stress?scenario=nasdaq_down_10` — stress test results
- [ ] `POST /api/portfolio/what-if` — hypothetical position diff (accepts symbol + quantity, returns before/after risk metrics)
- [ ] `POST /api/portfolio/explain` — LLM explanation for a specific metric (accepts metric key, returns cached or fresh explanation)

## Milestone 8: Data Pipeline

- [ ] Scheduled price refresh (daily OHLCV backfill + intraday current price)
- [ ] Indicator recalculation on new price data
- [ ] Portfolio risk recalculation on new indicator data
- [ ] LLM cache invalidation when underlying data changes
- [ ] Stale-data detection + user-facing "last updated" timestamp

## Milestone 9: Polish & Launch

- [ ] Loading skeletons for price/indicator fetches
- [ ] Error states (API down, invalid symbol, rate limit hit)
- [ ] LLM fallback UX — seamless degradation to deterministic explainers
- [ ] Dark mode
- [ ] PWA manifest + "Add to home screen"
- [ ] Open Graph / Twitter Card tags
- [ ] robots.txt + sitemap
- [ ] Lighthouse audit (perf, a11y, best practices)
