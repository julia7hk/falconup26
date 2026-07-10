# Features

Feature priority ladder, V0 → V2.

Status reflects what's shipped to prod. See
[milestones.md](milestones.md) for the breakdown into sprints.

---

## MVP (V0 — "portfolio intelligence platform")

- [ ] Portfolio dashboard — enter holdings (symbol + shares + avg cost),
      see current value, total P&L, and per-position gain/loss
- [ ] Per-symbol risk indicator panel — consolidate key metrics in one
      view: RSI, MACD, Bollinger Band width, 50/200-day SMA crossover,
      ATR (volatility), beta, Sharpe ratio, Sortino ratio (downside-only
      risk), max drawdown (worst peak-to-trough loss)
- [ ] Buy / Hold / Sell signal with confidence score — weighted
      composite of the indicators above, displayed as a clear badge per
      symbol
- [ ] Deterministic signal explainer — every recommendation shows *why*:
      which indicators fired, their current values, what threshold
      triggered the signal, and a plain-English template so you actually
      learn. Always available, no external dependency.
- [ ] Portfolio-level risk analysis — concentration score (Herfindahl
      index + sector breakdown), pairwise correlation matrix, effective
      leverage calculation, portfolio beta, max drawdown estimate, stress
      scenarios ("if Nasdaq drops 10%, your portfolio drops ~X%"),
      overall risk grade (A–F)
- [ ] Sector & correlation heatmap — visualize how your holdings
      correlate with each other and whether you're overexposed to a
      single sector (e.g. tech-heavy with QQQ + SOXL + TQQQ)
- [ ] What-if analysis — structured form (pick symbol + quantity) to
      model hypothetical trades before executing: "if I add 10 shares of
      AAPL, how does my portfolio risk change?" Shows before/after diff
      of all risk metrics.
- [ ] Structured LLM explainer — each risk metric has an "Explain"
      button that generates a contextual, personalized paragraph. No
      chat box, no free-text prompts. LLM receives precomputed risk data
      via versioned prompt templates and explains it in plain language.
      Output is validated (rejects hallucinated tickers), cached by data
      hash, and falls back to deterministic templates if LLM is
      unavailable. Framed as education, not financial advice.
- [ ] Support for ETFs *and* individual stocks — same indicator engine
      for both; default watchlist seeded with QQQ, TQQQ, SOXL
- [ ] Mobile-first responsive UI — usable on phone during market hours

## V0.5 — "make it sticky"

- [ ] Watchlist — add/remove symbols you're tracking but don't own yet;
      see the same indicator panel + signal without adding to portfolio
- [ ] Indicator deep-dive tooltips — tap any indicator for an
      educational popover: what it measures, how to read it, when it's
      most/least reliable, with a small illustrative chart
- [ ] Daily market summary — top-of-dashboard card summarizing today's
      macro picture: S&P 500, VIX, 10Y yield, fear & greed index

## V1 — "growth"

- [ ] Auth + cloud sync — sign up so portfolio and watchlist persist
      across devices
- [ ] Push / email notifications for triggered alerts
- [ ] Alert thresholds — set per-symbol alerts (e.g. "notify me if RSI
      drops below 30 or MACD crosses bullish")
- [ ] Historical signal chart — plot the buy/hold/sell signal over the
      last 30/90/180 days overlaid on price, so you can see how accurate
      the signals have been
- [ ] Backtesting — "if I had followed this signal for SYMBOL over the
      past 1/3/5 years, what would my return have been?" with equity
      curve chart
- [ ] Earnings calendar integration — flag upcoming earnings dates for
      holdings and watchlist, since volatility spikes around them
- [ ] News sentiment — pull recent headlines per symbol, run basic
      sentiment analysis, surface as an additional signal input

## V1.5 — "educate & build confidence"

- [ ] Learning center — short articles/cards explaining each indicator,
      portfolio concepts (diversification, rebalancing, dollar-cost
      averaging), and common mistakes
- [ ] Trade journal — log your buy/sell decisions and the reasoning;
      review later against actual outcomes to improve over time
- [ ] Guided stock screener — filter individual stocks by risk
      indicators, sector, market cap; designed for a beginner who
      doesn't know what to look for yet
- [ ] Weekly portfolio report (email) — automated summary of what moved,
      which signals changed, and what to pay attention to

## V2 — "expand"

- [ ] Options risk indicators — IV rank, put/call ratio, max pain for
      users who graduate to options
- [ ] Multi-portfolio support (e.g. taxable vs. Roth IRA)
- [ ] Social / compare — anonymously compare your portfolio risk profile
      against aggregate user base ("your portfolio is riskier than 70%
      of users")
- [ ] Broker integration (read-only via Plaid/broker API) — auto-import
      holdings instead of manual entry
- [ ] Export to CSV / PDF for tax prep or advisor review

## Defer / Probably Skip

- Automated trading / order execution (liability + regulatory minefield)
- Crypto support (different indicator set, different data sources — separate project)
- Social feed / community posts (stay focused on tools, not social)
- Paid stock-pick newsletters (conflicts with the "learn to decide for yourself" mission)
- Desktop-only features (mobile-first, period)
- AI chatbot / free-text chat interface (looks like an API wrapper, not engineering)

## Data Sources

Candidates for market data APIs (evaluate during V0):

1. [Yahoo Finance API](https://finance.yahoo.com) (unofficial, free,
   rate-limited)
2. [Alpha Vantage](https://www.alphavantage.co) (free tier: 25
   req/day)
3. [Twelve Data](https://twelvedata.com) (free tier: 800 req/day)
4. [Polygon.io](https://polygon.io) (free tier: 5 req/min, delayed)
5. [Finnhub](https://finnhub.io) (free tier: 60 req/min)
6. [FRED](https://fred.stlouisfed.org/docs/api/fred/) (macro data —
   VIX, yield curves, fed funds rate)
7. [Fear & Greed Index](https://edition.cnn.com/markets/fear-and-greed)
   (CNN, scrapeable)
