export type CatalogSymbol = {
  ticker: string;
  name: string;
  type: string;
  sector: string;
  leverage_factor: number;
  latest_close: number | null;
  latest_date: string | null;
};

export type PriceBar = {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

export type Quote = {
  symbol: string;
  price: number;
  change: number;
  change_percent: number;
  timestamp: string;
};

export type SectorInfo = {
  symbol: string;
  sector: string;
  industry: string;
  is_etf: boolean;
};

export type MacroSnapshot = {
  fed_funds_rate: number | null;
  vix: number | null;
  treasury_3mo: number | null;
  treasury_2y: number | null;
  treasury_10y: number | null;
  treasury_30y: number | null;
  as_of: string;
};

export type SearchResult = {
  symbol: string;
  name: string;
  type: string;
  exchange: string;
};

export type IndicatorData = {
  ticker: string;
  computed_at: string;
  data_points: number;
  indicators: {
    rsi?: { value: number; signal: string };
    macd?: { macd_line: number; signal_line: number; histogram: number; signal: string };
    bollinger?: { width: number; upper: number; lower: number; signal: string };
    sma_crossover?: { sma_50: number; sma_200: number; crossover_type: string; days_since_cross: number | null };
    atr?: { value: number; atr_percent: number };
    beta?: { value: number; interpretation: string };
    sharpe?: { value: number; risk_free_rate: number; interpretation: string };
    sortino?: { value: number; risk_free_rate: number; interpretation: string };
    max_drawdown?: { value: number; peak_date: string; trough_date: string };
  };
  composite: {
    score: number;
    signal: string;
    confidence: number;
    contributions: Record<string, number>;
    directions: Record<string, string>;
  };
};

export type Holding = {
  id: number;
  ticker: string;
  name: string;
  type: string;
  sector: string;
  leverage_factor: number;
  shares: number;
  avg_cost: number;
  cost_basis: number;
  price: number | null;
  change: number | null;
  change_percent: number | null;
  market_value: number | null;
  pnl: number | null;
  pnl_percent: number | null;
};

export type Portfolio = {
  holdings: Holding[];
  total_value: number;
  total_cost: number;
  total_pnl: number;
  prices_complete: boolean;
};

// GET /api/portfolio/value-history — dollar value of the current holdings on
// each past trading day. `complete` is false when a holding lacked price
// history and was excluded from the sum. `total_cost` is the flat cost basis.
export type PortfolioValuePoint = {
  date: string;
  value: number;
};

export type PortfolioValueHistory = {
  series: PortfolioValuePoint[];
  total_cost: number;
  holdings_count: number;
  complete: boolean;
};

export type RiskData = {
  concentration: {
    herfindahl_index: number;
    top_holding_pct: number;
    sector_breakdown: Record<string, number>;
    signal: string;
  } | null;
  effective_leverage: {
    value: number;
    leveraged_pct: number;
    signal: string;
  } | null;
  portfolio_beta: {
    value: number;
    interpretation: string;
  } | null;
  max_drawdown: {
    value: number;
    worst_start: string;
    worst_end: string;
    annualized_vol: number;
    signal: string;
  } | null;
  risk_grade: {
    grade: string;
    score: number;
    components: Record<string, { penalty: number; max_penalty: number; reason: string }>;
    interpretation: string;
  } | null;
  // Deterministic plain-English explanation of risk_grade, folded into the
  // /risk payload so the dashboard needn't re-fetch. Null when there's no grade.
  risk_grade_explanation: RiskExplanation | null;
  holdings_count: number;
};

export type RiskExplanationComponent = {
  key: string;
  label: string;
  penalty: number;
  max_penalty: number;
  severity: "none" | "low" | "moderate" | "high" | "severe";
  meaning: string; // educational "what this measures" (no figures)
  detail: string; // the engine's factual reason + a severity phrase
};

export type RiskExplanation = {
  grade: string;
  score: number;
  headline: string;
  overview: string;
  components: RiskExplanationComponent[];
  disclaimer: string;
};

// GET /api/portfolio/risk/explain. `available` is false (with a `message`)
// when no grade could be computed — no holdings, or <60 days of history.
export type RiskExplainResponse = {
  available: boolean;
  message: string | null;
  explanation: RiskExplanation | null;
  computed_at: string;
};

export type CorrelationData = {
  matrix: Record<string, Record<string, number>>;
  avg_pairwise: number | null;
  max_pair: [string, string, number] | null;
  tickers: string[];
  data_points: number;
  signal?: string;
};

export type StressScenario = {
  scenario_name: string;
  period: string;
  portfolio_impact_pct: number;
  portfolio_impact_dollar: number;
  holdings_impact: { ticker: string; return_pct: number | null; dollar_impact: number | null; note?: string }[];
};

export type StressData = {
  scenarios: StressScenario[];
  portfolio_value: number;
  disclaimer: string;
};

export type WhatIfRequest = {
  ticker: string;
  action: "buy" | "sell";
  quantity: number;
};

export type WhatIfDiffEntry = {
  before: number | null;
  after: number | null;
  delta: number | null;
  direction: "improved" | "worsened" | "unchanged" | "unavailable";
  // Only present on the risk_grade entry.
  before_grade?: string | null;
  after_grade?: string | null;
};

export type WhatIfResponse = {
  trade: WhatIfRequest;
  // before/after reuse the RiskData shape (same _compute_risk_metrics payload).
  before: RiskData;
  after: RiskData;
  diff: Record<string, WhatIfDiffEntry>;
  // Caveats about the comparison (e.g. drawdown not comparable for a
  // shorter-history buy). Empty when the whole diff is comparable.
  notes: string[];
  disclaimer: string;
};
