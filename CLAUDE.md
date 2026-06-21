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
- `docs/` — Features, milestones
- `kkulgag/` — Sibling project (Korean bulletin board aggregator), separate git repo. See `kkulgag/CLAUDE.md`.

## Dev Commands

### Backend (`backend/`)

```bash
uv sync                                          # install deps
uv run uvicorn main:app --reload --port 40401     # run dev server
uv run pytest                                     # all tests
uv add <package>                                  # add a dependency
uv add --dev <package>                            # add a dev dependency
```

### Database (from `backend/`)

```bash
uv run alembic revision -m "add foo table"        # new migration (hand-authored)
uv run alembic upgrade head                       # apply migrations
```

Never use `alembic revision --autogenerate` — Alembic migrations are the source of truth, ORM models are downstream.

## Stack

- **Backend:** FastAPI in `backend/`, managed by `uv`
- **DB:** Postgres. Schema owned by Alembic migrations (hand-authored). SQLAlchemy ORM.
- **Environment:** direnv + `.env` (see `.env.example` for all variables)

## Ports

- `WEB_PORT=4040` (Next.js — not yet set up)
- `FASTAPI_PORT=40401` (backend)

## Self-Maintenance Rule

After completing any feature, architectural shift, or major code correction, update this CLAUDE.md file to reflect the current state, updated test commands, or newly discovered pitfalls before closing the session.
