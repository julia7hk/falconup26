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
- `backend/llm/` — structured LLM layer (prompts/, context.py, validator.py, cache.py, client.py)
- `frontend/` — Next.js 16 (App Router) + React 19 + TypeScript + Tailwind 4
- `ops/` — Dockerfiles, Compose (`compose.build.yaml` for local dev, `compose.yaml` for production)
- `docs/` — Features, milestones
- `kkulgag/` — Sibling project (Korean bulletin board aggregator), separate git repo. See `kkulgag/CLAUDE.md`.

## Dev Commands

### Backend (from `backend/`)

```bash
uv sync                                          # install deps
uv run uvicorn main:app --reload --port 40401     # run dev server
uv run pytest                                     # all tests
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
- **DB:** Postgres 17 (hosted on nc01, not in Docker). Schema owned by Alembic migrations (hand-authored). SQLAlchemy ORM.
- **Infra:** Docker Compose in `ops/` — two services: `backend`, `frontend`. Postgres runs on the host (nc01), not in a container. Compose project name: `falconup-40`.
- **CI/CD:** GitHub Actions → build + push to GHCR → Jenkins webhook → nc01 pulls and redeploys. Images: `ghcr.io/julia7hk/falconup26/backend`, `ghcr.io/julia7hk/falconup26/frontend`
- **Environment:** direnv + `.env` (see `.env.example` for all variables)

## Ports

- `WEB_PORT=4040` (Next.js in `frontend/`)
- `FASTAPI_PORT=40401` (backend)
- Convention: project number 40 → ports 4**040** / 4**0401**

## Pitfalls

- **Next.js 16 breaking changes:** This project uses Next.js 16, which has breaking changes from earlier versions. Read `node_modules/next/dist/docs/` before writing frontend code. Do not assume APIs or conventions match Next.js 14/15.
- **No containerized Postgres:** Postgres runs on the host (nc01), not in Docker. Do not add a `db` service to Docker Compose. The backend container reaches host Postgres via the bridge network gateway (same pattern as kkulgag).
- **PGHOST in Docker:** `.env` has `PGHOST=localhost` which works for bare-metal dev but not inside containers. `compose.build.yaml` overrides it to `host.docker.internal` (Docker Desktop). On Linux/nc01 production, the `.env` on that host should set `PGHOST` to the bridge gateway IP (e.g. `172.17.0.1`).
- **NEXT_PUBLIC_* vars are build-time:** Next.js inlines `NEXT_PUBLIC_*` env vars into the JS bundle during `npm run build`. They must be passed as Docker build args (`ARG`/`ENV` in Dockerfile), not just runtime env vars. Changing them requires a rebuild.

## Self-Maintenance Rule

After completing any feature, architectural shift, or major code correction, update this CLAUDE.md file to reflect the current state, updated test commands, or newly discovered pitfalls before closing the session.
