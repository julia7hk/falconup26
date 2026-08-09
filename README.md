# FalconUp

Portfolio risk analysis for new investors. Scores a portfolio's risk from per-symbol indicators and portfolio-level stats, and explains the reasoning instead of just handing you a number.

🔗 [falconup.julia7hk.com](https://falconup.julia7hk.com/)

<img width="1679" height="819" alt="FalconUp landing page" src="https://github.com/user-attachments/assets/57317c29-73c4-40a2-8827-652c2a958729" />

## Why

I wanted to start investing in college and I wanted something that showed the risk I was taking and how it got there, so I could make informed decisions and actually learn how to invest. So I built it.

## Features

- **Per-symbol signal** — 9 indicators (RSI, MACD, Bollinger, SMA crossover, ATR, beta, Sharpe, Sortino, max drawdown) combined into one Buy/Hold/Sell read, with a breakdown of what each contributed.
- **Portfolio risk grade** — concentration, correlation, effective leverage, beta, and historical stress tests, scored A–F.
- **What-if simulator** — test a buy or sell against your portfolio and see the risk change. Doesn't touch the real portfolio.
- **Explainer** — each grade gets a plain-English "why", built deterministically from the engine's own numbers. An optional LLM layer rewords it, but only if a validator confirms every number and ticker still checks out; otherwise it falls back to the deterministic text. Not a chatbot.
- **Multi-user** — portfolios are per-account behind auth. Symbol catalog, indicators, and macro data are public.

## Architecture

The indicator and risk engines are pure functions with no DB or network access, so the math is tested on its own and I/O stays at the edges.

- `backend/indicators/` — indicator math + composite scoring
- `backend/risk/` — portfolio risk engine
- `backend/market/` — market data behind a provider interface (yfinance + FRED), Redis-cached
- `backend/llm_explainer/` — templates → LLM reword → validator → fallback, Anthropic call isolated to one file
- `backend/routers/` — FastAPI routes
- `frontend/` — Next.js UI

Alembic migrations are the source of truth for the schema; ORM models are downstream.

## Stack

FastAPI · Python 3.13 · Next.js 16 · React 19 · TypeScript · Tailwind 4 · PostgreSQL · Redis · Better Auth · Anthropic API · Docker · Nginx · Oracle Cloud · GitHub Actions

## Run it

```bash
# backend (from backend/)
uv sync
uv run uvicorn main:app --reload --port 40401
uv run pytest

# frontend (from frontend/)
npm install
npx prisma generate
npm run dev            # localhost:4040
```

Or `docker compose -f compose.build.yaml up --build` from `ops/`. Copy `.env.example` to `.env` first. Without `ANTHROPIC_API_KEY` the explainer just serves the deterministic text.
