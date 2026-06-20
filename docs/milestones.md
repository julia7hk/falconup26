# FalconUp Milestones — MVP

> **V0 핵심**: portfolio dashboard + risk indicators + buy/hold/sell signal with explainer. Post-MVP items in [features.md](features.md) (V0.5–V2).

## Milestone 1: Project Foundation

- [ ] Next.js (App Router) in `web/` — TypeScript + Tailwind, mobile-first
- [ ] FastAPI in `serv/` — Python 3.13
- [ ] Dev tooling (ruff, prettier, direnv, lefthook)
- [ ] Docker + Compose in `ops/`
- [ ] CI/CD pipeline
- [ ] Domain wiring + TLS

## Milestone 2: Data Source Integration

- [ ] Evaluate market data APIs (Yahoo Finance, Alpha Vantage, Twelve Data, Polygon, Finnhub)
- [ ] Select primary + fallback data source
- [ ] Price fetcher — current price, historical OHLCV (daily)
- [ ] Rate limiting + caching layer
- [ ] FRED integration for macro data (VIX, yield curves, fed funds rate)

## Milestone 3: Database & Data Model

- [ ] Alembic init in `serv/`
- [ ] Migration: `symbol` table (ticker, name, type: ETF/stock, sector)
- [ ] Migration: `portfolio_holding` table (symbol, shares, avg_cost)
- [ ] Migration: `price_history` table (symbol, date, OHLCV)
- [ ] Migration: `indicator_snapshot` table (symbol, date, indicator values)
- [ ] SQLAlchemy engine + async session
- [ ] Prisma init in `web/` + db pull + generate
- [ ] Seed default symbols (QQQ, TQQQ, SOXL)

## Milestone 4: Indicator Engine

- [ ] RSI (14-day)
- [ ] MACD (12/26/9)
- [ ] Bollinger Band width (20-day, 2σ)
- [ ] 50/200-day SMA crossover (golden cross / death cross)
- [ ] ATR (14-day volatility)
- [ ] Beta (vs S&P 500, 1-year)
- [ ] Sharpe ratio (1-year, risk-free rate from FRED)
- [ ] Composite signal score — weighted aggregate of all indicators
- [ ] Buy / Hold / Sell classification from composite score + confidence level

## Milestone 5: Signal Explainer

- [ ] Per-indicator status: current value, threshold that triggered, bullish/bearish/neutral
- [ ] Plain-English sentence per indicator ("RSI is 28 — below 30 indicates oversold, which is a bullish signal")
- [ ] Overall signal rationale ("3 of 7 indicators are bullish, 2 bearish, 2 neutral → Hold with low confidence")
- [ ] Indicator weight transparency — show how much each indicator contributed to the composite

## Milestone 6: Portfolio Dashboard — Frontend

- [ ] Add holding form (symbol lookup + shares + avg cost)
- [ ] Holdings list — current price, market value, P&L per position, gain/loss %
- [ ] Portfolio summary — total value, total P&L, day change
- [ ] Risk indicator panel per symbol — all 7 indicators in a compact card
- [ ] Buy/Hold/Sell badge per symbol with confidence score
- [ ] Signal explainer expandable per symbol
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

## Milestone 8: Data Pipeline

- [ ] Scheduled price refresh (daily OHLCV backfill + intraday current price)
- [ ] Indicator recalculation on new price data
- [ ] Stale-data detection + user-facing "last updated" timestamp

## Milestone 9: Polish & Launch

- [ ] Loading skeletons for price/indicator fetches
- [ ] Error states (API down, invalid symbol, rate limit hit)
- [ ] Dark mode
- [ ] PWA manifest + "Add to home screen"
- [ ] Open Graph / Twitter Card tags
- [ ] robots.txt + sitemap
- [ ] Lighthouse audit (perf, a11y, best practices)
