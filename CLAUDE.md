# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

FalconUp — portfolio intelligence platform for new/conservative investors. Per-symbol risk indicators (RSI, MACD, Bollinger, SMA crossover, ATR, beta, Sharpe) + portfolio-level risk analysis (concentration, correlation, effective leverage, stress scenarios) + structured LLM explainer layer (versioned prompts, output validation, deterministic fallback — no chatbot). See `docs/features.md` for the full feature ladder (V0–V2) and `docs/milestones.md` for sprint breakdown.

Project motivation context:
"i am a college student and i just got into investing. i dont really
know what im doing so i want to create a web app that consolidates a
lot of stock risk indicators, other tools, etc and tells me how my
position is and what actions i should take (buy/sell/hold) and is
also transparent about why it gave me that rating so i can learn and
improve. im not a very risk-taking person so i dont invest in
individual company stocks and own symbols like QQQ, SOXL, TQQQ, but
I would be open to investing in individual company stocks if I was
more educated and aware of what I was doing and had the confidence
and evidence to put money into it."

## Structure

- `backend/` — FastAPI + Python 3.13 (API, indicator engine, portfolio risk engine, LLM explainer)
- `backend/market/` — market data abstraction layer (provider protocol, yfinance impl, FRED macro data, Redis cache)
- `backend/routers/` — FastAPI route handlers (`symbols.py`, `macro.py`)
- `backend/llm/` — structured LLM layer (prompts/, context.py, validator.py, cache.py, client.py) — not yet implemented
- `frontend/` — Next.js 16 (App Router) + React 19 + TypeScript + Tailwind 4 — still boilerplate
- `ops/` — Dockerfiles, Compose (`compose.build.yaml` for local dev, `compose.yaml` for production), nginx config
- `docs/` — Features, milestones
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
npm run dev                                       # dev server on port 4040
npm run build                                     # production build
npm run lint                                      # ESLint
```

### Database (from `backend/`)

```bash
uv run alembic revision -m "add foo table"        # new migration (hand-authored)
uv run alembic upgrade head                       # apply migrations
```

Never use `alembic revision --autogenerate` — Alembic migrations are the source of truth, ORM models are downstream.

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

## Stack

- **Backend:** FastAPI in `backend/`, managed by `uv` (Python 3.13)
- **Frontend:** Next.js 16 (App Router, Turbopack) in `frontend/`, React 19, Tailwind 4
- **DB:** Postgres 16 (hosted on oc40, not in Docker). Schema owned by Alembic migrations (hand-authored). SQLAlchemy ORM. No migrations written yet.
- **Cache:** Redis (hosted on oc40, not in Docker). Used by `market/cache.py` for market data caching. `REDIS_URL` in `.env`. Tests use `fakeredis` (no running Redis needed).
- **Reverse proxy:** Nginx in Docker (`ops/nginx/conf.d/falconup.conf`). Path-based routing on `falconup.julia7hk.com`: `/api/*` → backend, everything else → Next.js. Only nginx exposes a host port (`${WEB_PORT}:80`); frontend and backend are internal to the Docker network.
- **TLS:** Cloudflare (edge termination). Domain `falconup.julia7hk.com` is proxied through Cloudflare; nginx listens on port 80. SSL mode: Full.
- **Infra:** Docker Compose in `ops/` — three services: `nginx`, `backend`, `frontend`. Postgres and Redis run on the host (oc40), not in containers. Compose project name: `falconup-40`. Server: Oracle Cloud free tier Ampere ARM64 instance (`ssh ubuntu@oc40`).
- **CI/CD:** GitHub Actions → build + push to GHCR. Images: `ghcr.io/julia7hk/falconup26/backend`, `ghcr.io/julia7hk/falconup26/frontend`. Deploy: pull on oc40 or build directly on oc40 with `compose.build.yaml`.
- **Environment:** direnv + `.env` (see `.env.example` for all variables)

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

## Ports

- Port 80 (nginx → exposed to host; proxies to frontend and backend)
- `FASTAPI_PORT=40401` (backend)
- Convention: project number 40 → ports 4**040** / 4**0401**

## Pitfalls

- **Next.js 16 breaking changes:** This project uses Next.js 16, which has breaking changes from earlier versions. Read `node_modules/next/dist/docs/` before writing frontend code. Do not assume APIs or conventions match Next.js 14/15.
- **No containerized Postgres or Redis:** Both run on the host (oc40), not in Docker. Do not add `db` or `redis` services to Docker Compose. The backend container reaches them via the Docker bridge gateway IP.
- **PGHOST in Docker:** `.env` has `PGHOST=localhost` which works for bare-metal dev but not inside containers. On Mac (Docker Desktop) set `PGHOST=host.docker.internal`. On oc40 (Linux) set `PGHOST=172.17.0.1` (Docker bridge gateway). Postgres `pg_hba.conf` and `listen_addresses` must allow connections from `172.16.0.0/12`.
- **REDIS_URL in Docker:** Same issue as PGHOST. `.env` has `REDIS_URL=redis://localhost:6379/0` which works for bare-metal dev. On oc40 set `REDIS_URL=redis://172.17.0.1:6379/0`. Redis `bind` config must include `172.17.0.1` (or `0.0.0.0`) and `protected-mode` should be `no` (or set a password).
- **NEXT_PUBLIC_* vars are build-time:** Next.js inlines `NEXT_PUBLIC_*` env vars into the JS bundle during `npm run build`. They must be passed as Docker build args (`ARG`/`ENV` in Dockerfile), not just runtime env vars. Changing them requires a rebuild.

## Self-Maintenance Rule

After completing any feature, architectural shift, or major code correction, update this CLAUDE.md file to reflect the current state, updated test commands, or newly discovered pitfalls before closing the session.
