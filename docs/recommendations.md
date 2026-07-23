# Recommendation / Action Layer

Turns the *diagnosis* (risk grade + explained penalties) into a *prescription*:
"here is the highest-impact thing to do with your next contribution, and here
is the simulated proof it helps." This closes the loop on the project's
founding promise — "tells me what actions I should take (buy/sell/hold) and is
transparent about why" — lifting it from the per-symbol signal to the whole
portfolio.

Not scheduled yet. This doc is the analysis + the design decisions to make
before it becomes a milestone.

## Why it fits now (it's mostly assembly, not new math)

Every primitive already ships:

- **M6 risk engine** measures risk and assigns a visible per-component penalty
  (concentration, correlation, leverage, beta, drawdown).
- **M7 what-if** applies a hypothetical trade and returns the before/after grade
  diff, reusing the engine. **This is the ranking primitive** — it can score any
  candidate move objectively.
- **M8 explainer** already names the worst components in plain English.

A recommendation is then four deterministic steps:

1. **Map** the flagged components → candidate remedy trades.
2. **Score** each candidate by running it through the what-if engine (Δ grade
   score).
3. **Rank** by improvement per dollar.
4. **Explain** each via the M8 template pattern (LLM rephrases later; never
   computes).

Because ranking is grounded in the actual simulated grade, the LLM never
produces a number or a ticker that isn't already in the structured result — the
same non-negotiable M8 enforces.

## Deterministic-first (same discipline as M8 and the signal explainer)

- **Candidate universe = the seeded `symbol` table only.** Suggestions can only
  name symbols the app knows, has price history for, and can run through the
  engine. This bounds the space and makes hallucinated picks structurally
  impossible.
- **Component → remedy mapping** (the human-readable "reason" layer):
  - *Concentration severe* (e.g. top holding 76%, HHI 0.62) → add broad-market
    exposure (VOO/VTI) or a holding in an under-weighted sector; optionally trim
    the top holding.
  - *Correlation severe* (e.g. QQQ/TQQQ ≈ 1.00) → add a genuinely uncorrelated
    asset class (bonds, international), **not** another tech fund. The
    correlation matrix already identifies the redundant pair.
  - *Leverage high* → reduce leveraged-ETF weight (e.g. shift TQQQ → QQQ).
  - *Beta high* → add lower-beta holdings.
  - *Drawdown high* → usually downstream of concentration + leverage; addressed
    indirectly by the above.
- **Ranking is empirical, not rule-of-thumb:** for each candidate trade at a
  given dollar size, re-run `_build_risk_data` / `_compute_risk_metrics` and take
  the Δ grade score. Rank by Δscore per dollar. Each suggestion carries its own
  simulated before/after as proof.
- A likely-better generalization of the rule map: **search the catalog** — try
  each seeded symbol as a hypothetical buy of the contribution amount, keep the
  top-N by Δscore. Still fully deterministic; the rule map becomes the
  explanation ("this reduces your single-sector concentration"), not the
  candidate generator.

## The goal question (do I need a target return + timeframe?)

**No — and deliberately not.**

- Risk-reduction suggestions are ranked by grade improvement, which is
  **goal-independent**. That's the tractable, safe v1.
- A return goal ("make X% in Y years") requires **predicting expected returns** —
  precisely what this project has avoided from day one. Risk is measurable from
  history; forward return is not reliably predictable. Optimizing toward a
  promised return is both a scope trap and a liability trap. Recommendations
  optimize **risk and diversification, never a target return.**
- **Contribution cadence is useful and safe**, though — the paycheck amount (and
  optionally frequency) *sizes* the suggested trade and frames it as
  dollar-cost-averaging into a better-diversified portfolio, which is exactly the
  right habit for a conservative beginner. So: capture a lightweight
  contribution amount; skip the return-goal input.

## Tax awareness (the "don't sell within a year" instinct)

The instinct is correct. In the US, **long-term capital gains** (asset held
> 1 year) are taxed at lower rates than **short-term gains** (held ≤ 1 year,
taxed as ordinary income). "Avoid selling within a year of buying" is a sound
default. Design consequences:

- **Prefer buy-side remedies** (steer new money) over sell-side. A buy creates no
  taxable event and doesn't disturb any holding-period clock — and it maps
  perfectly onto the contribution/paycheck model. **v1 = buy-only
  recommendations**, which also sidesteps tax complexity entirely.
- **Sell-side remedies need per-lot purchase dates** to warn about short-term
  gains. Today `portfolio_holding` stores only aggregate `shares` + `avg_cost`
  per (user, symbol) — no purchase date, no lots. Proper tax-aware sells require
  a schema addition (a purchase date, or a `lot` table). Defer. Until then, if a
  sell is ever suggested, surface only a generic "selling within a year of
  purchase may trigger higher short-term taxes" note.
- Tax treatment also depends on **account type** (taxable vs. Roth/IRA), which
  ties into the existing V2 "multi-portfolio" feature. Out of v1 scope; note it
  so the recommender's tax logic isn't built assuming a single account.

## The hard part: education vs. advice (liability)

The app is scrupulously framed as "analytical measurements, not financial
advice." Naming a specific security to a specific person based on their holdings
is much closer to **regulated personalized investment advice** (RIA / fiduciary
territory in the US). This doesn't kill the idea, but it dictates framing.
Extend M8's non-negotiables:

- **Educational scenarios, not directives.** "Portfolios concentrated in one
  sector are commonly diversified with broad-market or bond exposure — simulating
  adding VOO here would improve your grade from D to C." **Not** "Buy VOO."
- **Always show the simulated effect + the why.** Transparency is the core value;
  never emit a bare recommendation.
- **Never promise or project returns.** Rank on risk / diversification only.
- **Symbols are illustrative examples tied to categories** (broad-market, bonds,
  international), drawn from the seeded catalog — not hot picks.
- **Prominent, persistent not-financial-advice disclaimer** on the surface.

Goal-priority note: this is fine as a learning / personal-use tool (goals #1–2).
If it ever moves toward multi-user or monetization (#3–4), the advice framing
warrants a legal review before shipping. Flagged deliberately.

## Sequencing (mirror M8)

- **PR1 — deterministic.** Catalog search + what-if-based ranking + template
  explanations + a "Ways to improve" surface under the risk grade. No external
  API. The always-on baseline.
- **PR2 — LLM enrichment.** The LLM rephrases the ranked, already-simulated
  suggestions into friendlier prose; the validator rejects any ticker or number
  not present in the structured input; falls back to PR1 on any failure.

## Open questions (resolve before building)

- **Contribution input:** one-off "next contribution $" field vs. a saved cadence
  (amount + frequency)? Lean: start with a one-off amount, no persistence.
- **Candidate generation:** fixed rule map vs. catalog search (top-N by Δscore)?
  Lean: catalog search for candidates, rule map for the explanation.
- **Trade sizing for ranking:** fix the dollar amount at the contribution and
  rank, or solve for the amount that maximizes Δscore? Lean: fixed at the
  contribution amount.
- **Sells in v1?** Buy-only until per-lot tax tracking exists? Lean: buy-only.
- **How many suggestions?** Lean: top 3, ranked.
