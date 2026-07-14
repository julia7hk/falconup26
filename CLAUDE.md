# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

FalconUp — portfolio intelligence platform for new/conservative investors. Per-symbol risk indicators (RSI, MACD, Bollinger, SMA crossover, ATR, beta, Sharpe) + portfolio-level risk analysis (concentration, correlation, effective leverage, historical stress scenarios, transparent risk grade) + structured LLM explainer layer (versioned prompts, output validation, deterministic fallback — no chatbot). See `docs/features.md` for the full feature ladder (V0–V2) and `docs/milestones.md` for sprint breakdown.

Project motivation context:
"i am a college student and i just got into investing. i dont really know what
im doing so i want to create a web app that consolidates a lot of stock risk
indicators, other tools, etc and tells me how my position is and what actions i
should take (buy/sell/hold) and is also transparent about why it gave me that
rating so i can learn and improve. im not a very risk-taking person so i dont
invest in individual company stocks and own symbols like QQQ, SOXL, TQQQ, but I
would be open to investing in individual company stocks if I was more educated
and aware of what I was doing and had the confidence and evidence to put money
into it."

Project goals (priority order): learning & resume > personal use > multi-user > monetization. The app is deployed at `falconup.julia7hk.com` on oc40.

## Current Status

**Deployed** at `falconup.julia7hk.com` (oc40, Oracle Cloud Ampere ARM64). M1–M5.5 complete: project foundation, data sources, database, indicator engine, portfolio CRUD + frontend, auth + multi-tenancy. M6 (portfolio risk engine) complete: concentration, correlation, leverage, beta, drawdown, historical stress scenarios, transparent risk grade.

**Authentication is live.** Better Auth (Next.js) + FastAPI session bridge. Each user has their own portfolio. Public endpoints (`/api/symbols/*`, `/api/macro/*`) don't require auth. Portfolio endpoints (`/api/portfolio/*`) return 401 without a valid session. The main page is public — symbol catalog, indicators, lookup, and macro are visible without signing in; portfolio section only appears when logged in. See `docs/auth.md` for architecture.

## Structure

- `backend/` — FastAPI + Python 3.13 (API, indicator engine, portfolio risk engine, LLM explainer)
- `backend/market/` — market data abstraction layer (provider protocol, yfinance impl, FRED macro data, Redis cache)
- `backend/indicators/` — per-symbol indicator engine (models.py, math.py, composite.py). Pure functions, no DB dependency.
- `backend/risk/` — portfolio-level risk engine (models.py, math.py). Pure functions: concentration (HHI), correlation matrix, effective leverage, portfolio beta, max drawdown, historical stress test, risk grade. No DB dependency.
- `backend/routers/` — FastAPI route handlers (`symbols.py`, `macro.py`, `indicators.py`, `portfolio.py`, `risk.py`)
- `backend/auth.py` — `get_current_user` FastAPI dependency. Reads Better Auth session cookie, looks up shared `session` table in Postgres, returns user dict or 401.
- `backend/db.py` — SQLAlchemy async engine + session factory (asyncpg driver). Defers engine creation if `DATABASE_URL` is not set (safe for CI import).
- `backend/scripts/` — one-off CLI scripts (`seed.py`, `backfill.py`)
- `backend/llm/` — structured LLM layer (prompts/, context.py, validator.py, cache.py, client.py) — not yet implemented
- `frontend/` — Next.js 16 (App Router) + React 19 + TypeScript + Tailwind 4. Symbol catalog, sparkline charts, indicator panel, symbol lookup, macro snapshot, portfolio management (auth-gated).
- `frontend/src/lib/` — Prisma client (`db.ts`), Better Auth server config (`auth.ts`), Better Auth client (`auth-client.ts`)
- `frontend/prisma/` — Prisma schema (introspected from DB, not hand-authored). Regenerate with `npx prisma db pull`.
- `ops/` — Dockerfiles, Compose (`compose.build.yaml` for local dev, `compose.yaml` for production), nginx config
- `docs/` — Features, milestones, auth architecture
- `kkulgag/` — Sibling project (Korean bulletin board aggregator), separate git repo on nc01 (not oc40). See `kkulgag/CLAUDE.md`.

## Dev Commands

### Backend (from `backend/`)

```bash
uv sync                                          # install deps
uv run uvicorn main:app --reload --port 40401     # run dev server
uv run pytest                                     # all tests (fakeredis mocks Redis, no server needed)
uv run pytest tests/test_fred.py -v               # single test file
uv run pytest tests/test_fred.py::test_get_vix -v # single test
uv add <package>                                  # add a dependency
uv add --dev <package>                            # add a dev dependency
```

### Frontend (from `frontend/`)

```bash
npm install                                       # install deps
npx prisma db pull                                # introspect DB schema into prisma/schema.prisma
npx prisma generate                               # generate typed Prisma client (required before build)
npm run dev                                       # dev server on port 4040
npm run build                                     # production build
npm run lint                                      # ESLint
```

### Database (from `backend/`)

```bash
uv run alembic revision -m "add foo table"        # new migration (hand-authored)
uv run alembic upgrade head                       # apply migrations
uv run alembic current                            # check current migration state
uv run python -m scripts.seed                     # seed symbol table (16 symbols, idempotent)
uv run python -m scripts.backfill                 # backfill 5 years of price + macro history from yfinance/FRED
```

Never use `alembic revision --autogenerate` — Alembic migrations are the source of truth, ORM models are downstream.

Migrations use raw SQL (`op.execute("CREATE TABLE ...")`) — not SQLAlchemy API (`op.create_table(sa.Column(...))`).

### Docker (from `ops/`)

```bash
# Local dev (builds images from Dockerfiles)
docker compose -f compose.build.yaml up --build   # build + start all services
docker compose -f compose.build.yaml up -d        # start in daemon mode
docker compose -f compose.build.yaml down         # stop all services

# Production (pulls pre-built images from GHCR)
docker compose --env-file ../.env up -d            # start from registry images
docker compose --env-file ../.env down             # stop all services
```

### Deploy to oc40

After merging to main (pulls pre-built images from GHCR):

```bash
ssh ubuntu@oc40
cd ~/_proj/falconup26
git pull                                          # needed for bare-metal scripts (alembic, seed, backfill)
cd backend
# Bare-metal scripts need localhost, not Docker bridge IP
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/falconup uv run alembic upgrade head
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/falconup uv run python -m scripts.seed
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/falconup uv run python -m scripts.backfill
cd ../ops
docker compose --env-file ../.env down
docker compose --env-file ../.env pull            # pull latest images from ghcr.io
docker compose --env-file ../.env up -d
```

Alternative: build on-server instead of pulling from GHCR (slower, but works without registry access):

```bash
cd ops
docker compose -f compose.build.yaml down
docker compose -f compose.build.yaml up --build -d
```

## Stack

- **Backend:** FastAPI in `backend/`, managed by `uv` (Python 3.13)
- **Frontend:** Next.js 16 (App Router, Turbopack) in `frontend/`, React 19, Tailwind 4
- **Auth:** Better Auth (Next.js side) for registration/login/session management + Prisma adapter. FastAPI reads the shared `session` table via a session bridge (`backend/auth.py`). See `docs/auth.md`.
- **DB:** Postgres 16 (hosted on oc40, not in Docker). Schema owned by Alembic migrations (hand-authored). 8 tables: `symbol`, `portfolio_holding` (scoped by `user_id`), `price_history`, `macro_history`, plus Better Auth tables (`user`, `session`, `account`, `verification` — camelCase columns). Backend queries use raw SQL via `text()`. Frontend uses Prisma for server-side DB access (Better Auth adapter + typed queries).
- **Cache:** Redis (hosted on oc40, not in Docker). Used by `market/cache.py` for market data caching. `REDIS_URL` in `.env`. Tests use `fakeredis` (no running Redis needed).
- **Reverse proxy:** Nginx in Docker (`ops/nginx/conf.d/falconup.conf`). Path-based routing on `falconup.julia7hk.com`: `/api/auth/*` → Next.js (Better Auth), `/api/*` → FastAPI, everything else → Next.js. All locations set `X-Forwarded-Proto: https` (Cloudflare terminates TLS). Only nginx exposes a host port (`${WEB_PORT}:80`); frontend and backend are internal to the Docker network.
- **TLS:** Cloudflare (edge termination). Domain `falconup.julia7hk.com` is proxied through Cloudflare; nginx listens on port 80. SSL mode: Full.
- **Infra:** Docker Compose in `ops/` — three services: `nginx`, `backend`, `frontend`. Postgres and Redis run on the host (oc40), not in containers. Compose project name: `falconup-40`. Server: Oracle Cloud free tier Ampere ARM64 instance (`ssh ubuntu@oc40`).
- **CI/CD:** GitHub Actions → build + push to GHCR. Images: `ghcr.io/julia7hk/falconup26/backend`, `ghcr.io/julia7hk/falconup26/frontend`. Deploy: pull on oc40 or build directly on oc40 with `compose.build.yaml`.
- **Environment:** direnv + `.env` (see `.env.example` for all variables). Key auth vars: `BETTER_AUTH_SECRET` (random 32-byte base64), `NEXT_PUBLIC_BETTER_AUTH_URL` (points to frontend origin).

## Architecture

### Market Data Layer (`backend/market/`)

```
DataProvider (protocol)          → abstract interface for any data source
├── YFinanceProvider             → yfinance implementation (quotes, history, search, sector)
└── (future providers)           → swap by changing one line in fetcher.py

PriceFetcher                     → cached wrapper around any DataProvider
└── TTLCache (Redis-backed)      → pickle-serialized, prefix-namespaced keys (falconup:*)
    ├── quotes: 1 min TTL
    ├── history: 1 hour TTL
    ├── search: 24 hour TTL
    └── sector: 7 day TTL

FredProvider (separate)          → FRED API for macro data (fed funds, VIX, treasuries)
└── TTLCache (Redis-backed)      → 1 hour TTL (data changes at most once/day)
```

- `provider.py` — `DataProvider` protocol. Add new methods here when extending.
- `yfinance_provider.py` — concrete implementation. Includes `_ETF_CATEGORY_MAP` (17 hardcoded ETFs) for sector classification since yfinance doesn't return sectors for ETFs.
- `fetcher.py` — `PriceFetcher` wraps a provider with caching. Singleton via `@lru_cache`. The rest of the app imports `get_price_fetcher()`.
- `fred.py` — `FredProvider` for macro data. Singleton via `@lru_cache`. Requires `FRED_API_KEY` env var.
- `cache.py` — `TTLCache` backed by Redis with pickle serialization.
- `models.py` — `Quote`, `OHLCV`, `SectorInfo` dataclasses (frozen, slotted).

### Database Layer

```
Alembic migrations (source of truth)  → define schema
db.py                                 → async engine + session factory
routers/*.py                          → query via text() SQL, session from get_session() dependency
scripts/seed.py                       → populate symbol table (16 symbols, idempotent via ON CONFLICT)
scripts/backfill.py                   → pull 5yr OHLCV + FRED history into Postgres (idempotent)
```

Tables:
- `symbol` — ticker (unique), name, type (etf/stock), sector, industry, leverage_factor, timestamps
- `portfolio_holding` — user_id FK (text), symbol_id FK, shares, avg_cost, timestamps. UNIQUE on `(user_id, symbol_id)`.
- `price_history` — symbol_id FK, date, OHLCV, volume. Indexed + unique on (symbol_id, date)
- `macro_history` — series name, date, value. Indexed + unique on (series, date)
- `user` — Better Auth. text PK, name, email (unique), emailVerified, image, role, banned, timestamps. camelCase columns.
- `session` — Better Auth. token (unique), userId FK → user (CASCADE), expiresAt. Indexed on userId.
- `account` — Better Auth. Provider credentials (password, OAuth tokens). userId FK → user (CASCADE).
- `verification` — Better Auth. Email verification tokens.

Future tables:
- `indicator_snapshot` — M9 (data pipeline)
- `portfolio_risk_snapshot` — M9 (persist computed risk metrics on schedule; M6 computes on-the-fly)
- `llm_analysis_cache` — M8

### Indicator Engine (`backend/indicators/`)

```
models.py      → frozen dataclasses for each indicator result (RSIResult, MACDResult, etc.)
math.py        → 7 pure functions (rsi, macd, bollinger_width, sma_crossover, atr, beta, sharpe_ratio)
               → helpers: _ema, _sma
composite.py   → normalize_signal (each indicator → [-1,+1])
               → composite_score (weighted sum → Buy/Hold/Sell + confidence)
```

- All math functions take `list[float]` and return a result dataclass. No DB, no side effects.
- Beta requires SPY closes alongside the target symbol (pre-aligned by date via SQL JOIN).
- Sharpe uses the fed funds rate from `macro_history` as the risk-free rate.
- Composite weights: RSI 0.15, MACD 0.15, Bollinger 0.10, SMA 0.15, ATR 0.10, Beta 0.15, Sharpe 0.20.
- Missing indicators (insufficient data) are excluded and remaining weights re-normalized.
- Endpoint: `GET /api/symbols/{ticker}/indicators` computes on-the-fly (no caching/persistence yet).

### Portfolio Risk Engine (`backend/risk/`)

```
models.py      → frozen dataclasses (ConcentrationResult, CorrelationResult, etc.)
math.py        → 7 pure functions + predefined stress scenario date ranges
               → concentration, correlation_matrix, effective_leverage,
               → portfolio_beta, max_drawdown, historical_stress_test,
               → worst_period, risk_grade
```

- All math functions take plain Python types (lists, dicts, floats) and return result dataclasses. No DB, no side effects.
- Stress scenarios replay real historical events (COVID crash, 2022 tech selloff, etc.) using actual price data from `price_history`. No made-up shocks.
- Risk grade uses a transparent linear penalty system (100 - penalties = score). Each component (concentration, correlation, leverage, beta, drawdown) has a visible penalty with a plain-English reason.
- Grade thresholds (harsh): A >= 80, B >= 65, C >= 50, D >= 35, F < 35.
- Endpoints: `GET /api/portfolio/risk`, `GET /api/portfolio/correlation`, `GET /api/portfolio/stress?scenario=...` — all auth-gated.
- Computes on-the-fly (like indicators). Persistence deferred to M9.

### Data Flow

```
External APIs (yfinance, FRED)
  → backfill.py (one-time seed into Postgres)
  → Postgres (source of truth for historical data)
  → /api/symbols/{ticker}/history-db (serves from DB)

External APIs (yfinance, FRED)
  → Redis cache (short TTL, ephemeral)
  → /api/symbols/{ticker}/quote (live quotes, not stored in DB)
  → /api/macro/snapshot (live macro data)

Postgres (price_history + macro_history)
  → indicators/math.py (pure computation, on-the-fly)
  → /api/symbols/{ticker}/indicators (all 7 indicators + composite signal)

Postgres (portfolio_holding + symbol + price_history) + live quotes
  → risk/math.py (pure computation, on-the-fly)
  → /api/portfolio/risk (concentration, leverage, beta, drawdown, grade)
  → /api/portfolio/correlation (pairwise correlation matrix)
  → /api/portfolio/stress (historical scenario replay)
```

## Ports

- Port 80 (nginx → exposed to host; proxies to frontend and backend)
- `FASTAPI_PORT=40401` (backend)
- Convention: project number 40 → ports 4**040** / 4**0401**

## Pitfalls

- **Next.js 16 breaking changes:** This project uses Next.js 16, which has breaking changes from earlier versions. Read `node_modules/next/dist/docs/` before writing frontend code. Do not assume APIs or conventions match Next.js 14/15.
- **No containerized Postgres or Redis:** Both run on the host (oc40), not in Docker. Do not add `db` or `redis` services to Docker Compose. The backend container reaches them via the Docker bridge gateway IP.
- **PGHOST in Docker vs bare metal:** oc40's `.env` has `PGHOST=172.17.0.1` (Docker bridge gateway) for containers. Bare-metal commands (alembic, seed, backfill) need `localhost` — override with `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/falconup`. On Mac (Docker Desktop) use `PGHOST=host.docker.internal`.
- **REDIS_URL in Docker:** Same issue as PGHOST. On oc40: `REDIS_URL=redis://172.17.0.1:6379/0`. Redis `bind` config must include `172.17.0.1` (or `0.0.0.0`) and `protected-mode` should be `no` (or set a password).
- **DATABASE_URL for Prisma (frontend):** Same PGHOST pitfall as the backend. On oc40: `DATABASE_URL=postgresql://postgres:postgres@172.17.0.1:5432/falconup` (Docker bridge IP). Local dev on Mac: `host.docker.internal`. Bare-metal commands (`prisma db pull`, `prisma generate`): `localhost`.
- **NEXT_PUBLIC_* vars are build-time:** Next.js inlines `NEXT_PUBLIC_*` env vars into the JS bundle during `npm run build`. They must be passed as Docker build args (`ARG`/`ENV` in Dockerfile), not just runtime env vars. Changing them requires a rebuild.
- **db.py import safety:** `db.py` defers engine creation when `DATABASE_URL` is missing. This allows CI tests to import the app without a database. The error only fires at runtime when `get_session()` is called.
- **FRED date strings:** `FredProvider.get_series_history()` returns dates as ISO strings, not `date` objects. When inserting into Postgres via asyncpg, convert with `date.fromisoformat()` first.
- **React component definitions:** Do not define React components inside other components — Next.js 16 ESLint will flag this and it causes state reset on every render. Define them at module scope.
- **Auth cookie name varies by protocol:** In production (HTTPS), Better Auth prefixes the cookie with `__Secure-` → `__Secure-better-auth.session_token`. In local dev (HTTP), it's just `better-auth.session_token`. The session bridge in `auth.py` checks both. If auth works locally but fails in prod (401 on every portfolio request), this is likely the cause.
- **Prisma generate required before frontend build:** `npx prisma generate` must run before `npm run build`. The Dockerfile does this automatically. CI does it as a separate step. Forgetting it locally causes import errors for `@/generated/prisma/client`.
- **Next.js rewrite excludes /api/auth/:** `next.config.ts` rewrites `/api/*` to FastAPI, but excludes `/api/auth/*` so Better Auth's catchall route handler works. If a new `/api/auth/*` endpoint is added to FastAPI, it won't be reachable.
- **Better Auth tables use camelCase:** The `user`, `session`, `account`, `verification` tables have camelCase column names (e.g. `userId`, `expiresAt`) to match Better Auth's Prisma adapter. The rest of the schema uses snake_case.

## Ideas Under Consideration

### Pension fund coattail tracking

Track holdings of major pension funds (국민연금/NPS, CPP, CalPERS, etc.) as a "smart money" signal for beginner investors. The thesis: these funds have professional analysts, long horizons, and fiduciary obligations — following their moves is a legitimate strategy. Open questions before this is actionable:

- **Data sources:** NPS reports via DART/FSS (Korean), SEC 13F (US institutional), CalPERS quarterly reports. Each has different format, update schedule, and API. Significantly more data engineering than current yfinance/FRED setup.
- **Disclosure lag:** 13F filings are 45 days delayed, NPS quarterly/monthly. By the time data is visible, the trade is old.
- **Scale mismatch:** Pension fund positions (billions) don't map directly to retail ETF decisions.
- **Signal-to-action gap:** Needs an interpretation layer to translate "NPS bought Samsung" into something actionable for a QQQ/TQQQ holder.
- **Starting point:** If pursued, start with SEC 13F data only (free APIs exist, e.g. SEC EDGAR) and frame as "institutional activity" rather than multi-country pension aggregation.

## Self-Maintenance Rule

After completing any feature, architectural shift, or major code correction, update this CLAUDE.md file to reflect the current state, updated test commands, or newly discovered pitfalls before closing the session.
