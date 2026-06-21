# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

FalconUp — investment risk indicator web app. The workspace also contains a sibling project (`kkulgag/`) with its own git repo.

- `docs/features.md` — Feature spec and priority ladder (V0–V2)
- `kkulgag/` — Separate project (Korean bulletin board aggregator). See `kkulgag/CLAUDE.md` for its dev commands and architecture.

## kkulgag Quick Reference

Full details in `kkulgag/CLAUDE.md`. Key points:

- **Stack:** Next.js (App Router) + Tailwind frontend (`web/`), FastAPI + Python 3.13 backend (`serv/`), Postgres, Prefect pipelines
- **Run all:** `hivemind` from `kkulgag/` (ports 4030 web, 40301 API)
- **Backend:** `cd serv && poetry install && PYTHONPATH=. poetry run pytest`
- **Frontend:** `cd web && npm install && npm run dev`
- **Formatting:** Python → `ruff`, TypeScript → `prettier`
- **DB schema:** Alembic migrations are source of truth; ORM models (SQLAlchemy, Prisma) are regenerated downstream. Never use `--autogenerate`.
- **CI:** GitLab CI → Docker build → Jenkins webhook → deploy to nc01

## FalconUp (Planned)

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

Investment risk indicator app targeting new/conservative investors. See `docs/features.md` for the full feature ladder (V0–V2). MVP scope:

- Portfolio dashboard (holdings, P&L)
- Risk indicator panel (RSI, MACD, Bollinger, SMA crossover, ATR, beta, Sharpe)
- Buy/Hold/Sell signal with confidence score and explainer
- ETF + individual stock support (default watchlist: QQQ, TQQQ, SOXL)
- Mobile-first responsive UI

Data source candidates listed in `docs/features.md` (Yahoo Finance, Alpha Vantage, Twelve Data, Polygon, Finnhub, FRED).

## Database

- **DB:** Postgres. Schema owned by Alembic migrations in `backend/` (hand-authored). Never use `alembic revision --autogenerate`.
- **Backend ORM:** SQLAlchemy in `backend/`
- **Package manager:** `uv` (not poetry)

## Self-Maintenance Rule
After completing any feature, architectural shift, or major code correction, update this CLAUDE.md file to reflect the current state, updated test commands, or newly discovered pitfalls before closing the session.
