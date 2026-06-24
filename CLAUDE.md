# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

FalconUp — investment risk indicator web app for new/conservative investors. Portfolio dashboard, risk indicators (RSI, MACD, Bollinger, SMA crossover, ATR, beta, Sharpe), buy/hold/sell signals with explainers. See `docs/features.md` for the full feature ladder (V0–V2) and `docs/milestones.md` for sprint breakdown.

Project motivation context:
"i am a college student and i just got into investing. i dont
really know what im doing so i want to create a web app that
consolidates a lot of stock risk indicators and other tools and
whatnot and tells me how my position is and what actions i should
take (buy/sell/hold) and is also transparent about why it gave me
that rating so i can learn and improve. im not a very risk-taking
person so i dont invest in individual company stocks and own
symbols like QQQ SOXL and TQQQ, but I would be open to investing
in individual company stocks if I was more educated and aware of
what I was doing and had the confidence and evidence to put money
into it."

## Structure

- `backend/` — FastAPI + Python 3.13 (API, indicator engine)
- `frontend/` — Next.js 16 (App Router) + React 19 + TypeScript + Tailwind 4
- `ops/` — Docker Compose (Postgres, backend, frontend)
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
docker compose up --build                         # build + start all services
docker compose up                                 # start (reuse existing images)
docker compose down                               # stop all services
docker compose down -v                            # stop + delete database volume
```

## Stack

- **Backend:** FastAPI in `backend/`, managed by `uv` (Python 3.13)
- **Frontend:** Next.js 16 (App Router, Turbopack) in `frontend/`, React 19, Tailwind 4
- **DB:** Postgres 17. Schema owned by Alembic migrations (hand-authored). SQLAlchemy ORM.
- **Infra:** Docker Compose in `ops/` — three services: `db`, `backend`, `frontend`
- **Environment:** direnv + `.env` (see `.env.example` for all variables)

## Ports

- `WEB_PORT=4040` (Next.js in `frontend/`)
- `FASTAPI_PORT=40401` (backend)

## Pitfalls

- **Next.js 16 breaking changes:** This project uses Next.js 16, which has breaking changes from earlier versions. Read `node_modules/next/dist/docs/` before writing frontend code. Do not assume APIs or conventions match Next.js 14/15.
- **Docker PGHOST:** In Docker Compose, backend connects to Postgres via hostname `db` (the service name), not `localhost`. The compose file overrides `PGHOST=db`.

## Self-Maintenance Rule

After completing any feature, architectural shift, or major code correction, update this CLAUDE.md file to reflect the current state, updated test commands, or newly discovered pitfalls before closing the session.
