"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { authClient } from "@/lib/auth-client";

type CatalogSymbol = {
  ticker: string;
  name: string;
  type: string;
  sector: string;
  leverage_factor: number;
  latest_close: number | null;
  latest_date: string | null;
};

type PriceBar = {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

type Quote = {
  symbol: string;
  price: number;
  change: number;
  change_percent: number;
  timestamp: string;
};

type SectorInfo = {
  symbol: string;
  sector: string;
  industry: string;
  is_etf: boolean;
};

type MacroSnapshot = {
  fed_funds_rate: number | null;
  vix: number | null;
  treasury_3mo: number | null;
  treasury_2y: number | null;
  treasury_10y: number | null;
  treasury_30y: number | null;
  as_of: string;
};

type SearchResult = {
  symbol: string;
  name: string;
  type: string;
  exchange: string;
};

type IndicatorData = {
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
  };
  composite: {
    score: number;
    signal: string;
    confidence: number;
    contributions: Record<string, number>;
    directions: Record<string, string>;
  };
};

type Holding = {
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

type Portfolio = {
  holdings: Holding[];
  total_value: number;
  total_cost: number;
  total_pnl: number;
  prices_complete: boolean;
};

function Sparkline({ data }: { data: PriceBar[] }) {
  if (data.length < 2) return null;
  const closes = data.map((d) => d.close);
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const range = max - min || 1;
  const w = 600;
  const h = 120;
  const points = closes
    .map((c, i) => {
      const x = (i / (closes.length - 1)) * w;
      const y = h - ((c - min) / range) * (h - 10) - 5;
      return `${x},${y}`;
    })
    .join(" ");
  const trending = closes[closes.length - 1] >= closes[0];
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-48">
      <polyline
        fill="none"
        stroke={trending ? "#22c55e" : "#ef4444"}
        strokeWidth="2"
        points={points}
      />
    </svg>
  );
}

function SignalBadge({ signal }: { signal: string }) {
  const colors: Record<string, string> = {
    bullish: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
    oversold: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
    low_volatility: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
    bearish: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
    overbought: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
    high_volatility: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
    neutral: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400",
  };
  return (
    <span
      className={`rounded px-1.5 py-0.5 text-xs font-medium ${colors[signal] ?? colors.neutral}`}
    >
      {signal.replace("_", " ")}
    </span>
  );
}

function IndicatorCard({
  name,
  value,
  signal,
  detail,
}: {
  name: string;
  value: string;
  signal: string;
  detail: string;
}) {
  return (
    <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-zinc-500 dark:text-zinc-400">
          {name}
        </p>
        <SignalBadge signal={signal} />
      </div>
      <p className="mt-1 font-mono text-lg font-semibold dark:text-white">
        {value}
      </p>
      <p className="mt-0.5 text-xs text-zinc-400">{detail}</p>
    </div>
  );
}

function CompositeCard({ indicators }: { indicators: IndicatorData }) {
  const [expanded, setExpanded] = useState(false);
  const { composite } = indicators;
  const directions = Object.values(composite.directions);
  const bullishCount = directions.filter((d) => d === "bullish").length;
  const bearishCount = directions.filter((d) => d === "bearish").length;
  const neutralCount = directions.filter((d) => d === "neutral").length;

  return (
    <div
      className={`rounded-lg border ${
        composite.signal === "buy"
          ? "border-green-300 bg-green-50 dark:border-green-700 dark:bg-green-950"
          : composite.signal === "sell"
            ? "border-red-300 bg-red-50 dark:border-red-700 dark:bg-red-950"
            : "border-zinc-200 bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900"
      }`}
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full p-5 text-left"
      >
        <div className="flex items-center justify-between">
          <div>
            <span
              className={`text-2xl font-bold uppercase ${
                composite.signal === "buy"
                  ? "text-green-700 dark:text-green-400"
                  : composite.signal === "sell"
                    ? "text-red-700 dark:text-red-400"
                    : "text-zinc-600 dark:text-zinc-300"
              }`}
            >
              {composite.signal}
            </span>
            <span className="ml-3 text-sm text-zinc-500 dark:text-zinc-400">
              Confidence: {(composite.confidence * 100).toFixed(0)}%
            </span>
            <span className="ml-2 text-xs text-zinc-400">{expanded ? "▲" : "▼"}</span>
          </div>
          <div className="text-right">
            <p className="font-mono text-lg font-semibold dark:text-zinc-200">
              {composite.score > 0 ? "+" : ""}
              {composite.score.toFixed(3)}
            </p>
            <p className="text-xs text-zinc-400">composite score</p>
          </div>
        </div>
      </button>
      {expanded && (
        <div className="border-t border-inherit px-5 pb-5 pt-3">
          <p className="text-sm leading-relaxed text-zinc-600 dark:text-zinc-300">
            This signal combines all 7 indicators into a single recommendation using a weighted average.
            Each indicator is scored from -1 (bearish) to +1 (bullish), then multiplied by its weight.
            The composite score ({composite.score > 0 ? "+" : ""}{composite.score.toFixed(3)}) is the weighted average.
            {composite.signal === "buy"
              ? " A score above +0.15 triggers a Buy signal."
              : composite.signal === "sell"
                ? " A score below -0.15 triggers a Sell signal."
                : " A score between -0.15 and +0.15 means Hold — no strong direction."}
          </p>
          <p className="mt-2 text-sm leading-relaxed text-zinc-600 dark:text-zinc-300">
            Right now, {bullishCount} indicator{bullishCount !== 1 ? "s" : ""} {bullishCount !== 1 ? "are" : "is"} bullish,
            {" "}{bearishCount} {bearishCount !== 1 ? "are" : "is"} bearish
            {neutralCount > 0 ? `, and ${neutralCount} ${neutralCount !== 1 ? "are" : "is"} neutral` : ""}.
            {" "}Confidence ({(composite.confidence * 100).toFixed(0)}%) reflects how strongly the indicators agree —
            {composite.confidence < 0.3
              ? " it's low because the indicators are giving mixed signals. This means the data doesn't point clearly in one direction."
              : composite.confidence < 0.6
                ? " it's moderate, meaning most indicators lean the same way but there's some disagreement."
                : " it's high, meaning the indicators are mostly in agreement."}
          </p>
          <div className="mt-3 text-xs text-zinc-400">
            <p className="font-medium">Weights: RSI 15% · MACD 15% · Bollinger 10% · SMA 15% · ATR 10% · Beta 15% · Sharpe 20%</p>
          </div>
        </div>
      )}
    </div>
  );
}

export default function Home() {
  const router = useRouter();
  const { data: session } = authClient.useSession();
  const [catalog, setCatalog] = useState<CatalogSymbol[]>([]);
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [history, setHistory] = useState<PriceBar[]>([]);
  const [historyDays, setHistoryDays] = useState(365);
  const [symbol, setSymbol] = useState("");
  const [quote, setQuote] = useState<Quote | null>(null);
  const [sector, setSector] = useState<SectorInfo | null>(null);
  const [macro, setMacro] = useState<MacroSnapshot | null>(null);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [indicators, setIndicators] = useState<IndicatorData | null>(null);
  const [indicatorsLoading, setIndicatorsLoading] = useState(false);
  const [indicatorsError, setIndicatorsError] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [addTicker, setAddTicker] = useState("");
  const [addShares, setAddShares] = useState("");
  const [addAvgCost, setAddAvgCost] = useState("");
  const [addError, setAddError] = useState("");
  const [addLoading, setAddLoading] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editShares, setEditShares] = useState("");
  const [editAvgCost, setEditAvgCost] = useState("");
  const [portfolioError, setPortfolioError] = useState("");
  const [holdingSignals, setHoldingSignals] = useState<Record<string, { signal: string; confidence: number }>>({});

  useEffect(() => {
    fetch("/api/symbols/catalog")
      .then((res) => res.json())
      .then(setCatalog)
      .catch(() => {});
  }, []);

  // Fetch portfolio only when signed in
  useEffect(() => {
    if (session) fetchPortfolio();
  }, [session]);

  async function fetchPortfolio() {
    try {
      const res = await fetch("/api/portfolio", { credentials: "include" });
      if (!res.ok) return;
      const data: Portfolio = await res.json();
      setPortfolio(data);

      // Fetch indicators for each holding (fire-and-forget, non-blocking)
      const tickers = data.holdings.map((h) => h.ticker);
      const signals: Record<string, { signal: string; confidence: number }> = {};
      await Promise.all(
        tickers.map(async (ticker) => {
          try {
            const r = await fetch(`/api/symbols/${ticker}/indicators`);
            if (r.ok) {
              const ind: IndicatorData = await r.json();
              signals[ticker] = {
                signal: ind.composite.signal,
                confidence: ind.composite.confidence,
              };
            }
          } catch {}
        }),
      );
      setHoldingSignals(signals);
    } catch {}
  }

  async function addHolding() {
    if (!addTicker.trim() || !addShares || !addAvgCost) return;
    const shares = parseFloat(addShares);
    const avgCost = parseFloat(addAvgCost);
    if (isNaN(shares) || shares <= 0 || isNaN(avgCost) || avgCost <= 0) {
      setAddError("Shares and avg cost must be positive numbers");
      return;
    }
    setAddError("");
    setAddLoading(true);
    try {
      const res = await fetch("/api/portfolio/holdings", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticker: addTicker.toUpperCase(),
          shares: parseFloat(addShares),
          avg_cost: parseFloat(addAvgCost),
        }),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || `Failed (${res.status})`);
      }
      setAddTicker("");
      setAddShares("");
      setAddAvgCost("");
      setShowAddForm(false);
      await fetchPortfolio();
    } catch (e) {
      setAddError(e instanceof Error ? e.message : "Failed to add holding");
    } finally {
      setAddLoading(false);
    }
  }

  async function updateHolding(id: number) {
    setPortfolioError("");
    try {
      const shares = editShares ? parseFloat(editShares) : undefined;
      const avgCost = editAvgCost ? parseFloat(editAvgCost) : undefined;
      if ((shares !== undefined && (isNaN(shares) || shares <= 0)) ||
          (avgCost !== undefined && (isNaN(avgCost) || avgCost <= 0))) {
        setPortfolioError("Shares and avg cost must be positive numbers");
        return;
      }
      const body: Record<string, number> = {};
      if (shares !== undefined) body.shares = shares;
      if (avgCost !== undefined) body.avg_cost = avgCost;
      const res = await fetch(`/api/portfolio/holdings/${id}`, {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || `Update failed (${res.status})`);
      }
      setEditingId(null);
      await fetchPortfolio();
    } catch (e) {
      setPortfolioError(e instanceof Error ? e.message : "Failed to update holding");
    }
  }

  async function deleteHolding(id: number) {
    setPortfolioError("");
    try {
      const res = await fetch(`/api/portfolio/holdings/${id}`, { method: "DELETE", credentials: "include" });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || `Delete failed (${res.status})`);
      }
      await fetchPortfolio();
    } catch (e) {
      setPortfolioError(e instanceof Error ? e.message : "Failed to delete holding");
    }
  }

  async function selectSymbol(ticker: string, days = historyDays) {
    const isNewTicker = ticker !== selectedTicker;
    setSelectedTicker(ticker);
    if (isNewTicker) {
      setIndicators(null);
      setIndicatorsLoading(true);
      setIndicatorsError("");
    }
    try {
      const fetches: Promise<Response>[] = [
        fetch(`/api/symbols/${ticker}/history-db?days=${days}`),
      ];
      if (isNewTicker) {
        fetches.push(fetch(`/api/symbols/${ticker}/indicators`));
      }
      const results = await Promise.all(fetches);
      if (results[0].ok) setHistory(await results[0].json());
      if (isNewTicker) {
        if (results[1]?.ok) {
          setIndicators(await results[1].json());
        } else {
          setIndicatorsError(`Could not load indicators (${results[1]?.status ?? "network error"})`);
        }
      }
    } catch {
      if (isNewTicker) setIndicatorsError("Failed to fetch indicators");
    } finally {
      if (isNewTicker) setIndicatorsLoading(false);
    }
  }

  async function lookupSymbol() {
    if (!symbol.trim()) return;
    setError("");
    setLoading(true);
    setSearchResults([]);
    try {
      const [quoteRes, sectorRes] = await Promise.all([
        fetch(`/api/symbols/${symbol}/quote`),
        fetch(`/api/symbols/${symbol}/sector`),
      ]);
      if (!quoteRes.ok) throw new Error(`Quote failed: ${quoteRes.status}`);
      setQuote(await quoteRes.json());
      if (sectorRes.ok) setSector(await sectorRes.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Lookup failed");
      setQuote(null);
      setSector(null);
    } finally {
      setLoading(false);
    }
  }

  async function searchSymbols() {
    if (!symbol.trim()) return;
    setError("");
    try {
      const res = await fetch(`/api/symbols/search?q=${symbol}`);
      if (!res.ok) throw new Error(`Search failed: ${res.status}`);
      setSearchResults(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Search failed");
    }
  }

  async function loadMacro() {
    setError("");
    try {
      const res = await fetch("/api/macro/snapshot");
      if (!res.ok) throw new Error(`Macro failed: ${res.status}`);
      setMacro(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Macro fetch failed");
    }
  }

  return (
    <div className="flex flex-col flex-1 items-center bg-zinc-50 font-sans dark:bg-zinc-950">
      <main className="flex flex-1 w-full max-w-6xl flex-col gap-10 py-12 px-8">
        <div className="flex items-center justify-between">
          <h1 className="text-4xl font-bold tracking-tight dark:text-white">
            FalconUp
          </h1>
          {session ? (
            <div className="flex items-center gap-3">
              <a
                href="/profile"
                className="text-sm text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200"
              >
                {session.user.name || session.user.email}
              </a>
              <button
                onClick={async () => {
                  await authClient.signOut();
                  router.refresh();
                }}
                className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm text-zinc-600 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-800"
              >
                Sign Out
              </button>
            </div>
          ) : (
            <a
              href="/sign-in"
              className="rounded-lg bg-zinc-900 px-4 py-1.5 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
            >
              Sign In
            </a>
          )}
        </div>

        {/* Portfolio — only visible when signed in */}
        {session && <section className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold dark:text-zinc-200">
              My Portfolio
              {portfolio && portfolio.holdings.length > 0 && (
                <span className="ml-2 text-base font-normal text-zinc-400">
                  {portfolio.holdings.length} holding{portfolio.holdings.length !== 1 ? "s" : ""}
                </span>
              )}
            </h2>
            <button
              onClick={() => setShowAddForm(!showAddForm)}
              className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
            >
              {showAddForm ? "Cancel" : "+ Add Holding"}
            </button>
          </div>

          {/* Add Holding Form */}
          {showAddForm && (
            <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-700">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                <div className="flex-1">
                  <label className="mb-1 block text-sm text-zinc-500 dark:text-zinc-400">Symbol</label>
                  <input
                    type="text"
                    value={addTicker}
                    onChange={(e) => setAddTicker(e.target.value.toUpperCase())}
                    placeholder="e.g. QQQ"
                    className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-white"
                  />
                </div>
                <div className="flex-1">
                  <label className="mb-1 block text-sm text-zinc-500 dark:text-zinc-400">Shares</label>
                  <input
                    type="number"
                    value={addShares}
                    onChange={(e) => setAddShares(e.target.value)}
                    placeholder="10"
                    min="0"
                    step="any"
                    className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-white"
                  />
                </div>
                <div className="flex-1">
                  <label className="mb-1 block text-sm text-zinc-500 dark:text-zinc-400">Avg Cost ($)</label>
                  <input
                    type="number"
                    value={addAvgCost}
                    onChange={(e) => setAddAvgCost(e.target.value)}
                    placeholder="480.00"
                    min="0"
                    step="any"
                    className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-white"
                  />
                </div>
                <button
                  onClick={addHolding}
                  disabled={addLoading}
                  className="rounded-lg bg-zinc-900 px-5 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
                >
                  {addLoading ? "Adding..." : "Add"}
                </button>
              </div>
              {addError && (
                <p className="mt-2 text-sm text-red-600 dark:text-red-400">{addError}</p>
              )}
              <p className="mt-2 text-xs text-zinc-400">
                Symbol must be in the database. Try: QQQ, TQQQ, SOXL, SPY, AAPL, MSFT, NVDA, GOOGL, AMZN, META, TSLA
              </p>
            </div>
          )}

          {/* Portfolio Error */}
          {portfolioError && (
            <p className="text-sm text-red-600 dark:text-red-400">{portfolioError}</p>
          )}

          {/* Portfolio Summary */}
          {portfolio && portfolio.holdings.length > 0 && (
            <>
              {!portfolio.prices_complete && (
                <p className="text-sm text-amber-600 dark:text-amber-400">
                  Some prices are unavailable — totals may be incomplete.
                </p>
              )}
              <div className="grid grid-cols-3 gap-3">
                <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
                  <p className="text-sm text-zinc-500 dark:text-zinc-400">Total Value</p>
                  <p className="font-mono text-xl font-semibold dark:text-white">
                    ${portfolio.total_value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </p>
                </div>
                <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
                  <p className="text-sm text-zinc-500 dark:text-zinc-400">Total Cost</p>
                  <p className="font-mono text-xl font-semibold dark:text-white">
                    ${portfolio.total_cost.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </p>
                </div>
                <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
                  <p className="text-sm text-zinc-500 dark:text-zinc-400">Total P&L</p>
                  <p className={`font-mono text-xl font-semibold ${
                    portfolio.total_pnl >= 0
                      ? "text-green-600 dark:text-green-400"
                      : "text-red-600 dark:text-red-400"
                  }`}>
                    {portfolio.total_pnl >= 0 ? "+" : ""}
                    ${portfolio.total_pnl.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </p>
                </div>
              </div>
            </>
          )}

          {/* Holdings List */}
          {portfolio && portfolio.holdings.length > 0 ? (
            <div className="flex flex-col gap-3">
              {portfolio.holdings.map((h) => (
                <div
                  key={h.id}
                  className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-700"
                >
                  {editingId === h.id ? (
                    /* Edit mode */
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                      <div>
                        <p className="font-mono text-lg font-bold dark:text-white">{h.ticker}</p>
                        <p className="text-sm text-zinc-400">{h.name}</p>
                      </div>
                      <div className="flex-1">
                        <label className="mb-1 block text-xs text-zinc-400">Shares</label>
                        <input
                          type="number"
                          value={editShares}
                          onChange={(e) => setEditShares(e.target.value)}
                          min="0"
                          step="any"
                          className="w-full rounded border border-zinc-300 px-2 py-1 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-white"
                        />
                      </div>
                      <div className="flex-1">
                        <label className="mb-1 block text-xs text-zinc-400">Avg Cost ($)</label>
                        <input
                          type="number"
                          value={editAvgCost}
                          onChange={(e) => setEditAvgCost(e.target.value)}
                          min="0"
                          step="any"
                          className="w-full rounded border border-zinc-300 px-2 py-1 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-white"
                        />
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={() => updateHolding(h.id)}
                          className="rounded bg-zinc-900 px-3 py-1 text-sm text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900"
                        >
                          Save
                        </button>
                        <button
                          onClick={() => setEditingId(null)}
                          className="rounded border border-zinc-300 px-3 py-1 text-sm hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    /* Display mode */
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <div>
                          <div className="flex items-baseline gap-2">
                            <span
                              className="cursor-pointer font-mono text-lg font-bold hover:text-blue-600 dark:text-white dark:hover:text-blue-400"
                              onClick={() => selectSymbol(h.ticker)}
                            >
                              {h.ticker}
                            </span>
                            {h.leverage_factor !== 1 && (
                              <span className="rounded bg-amber-100 px-1 text-xs font-medium text-amber-700 dark:bg-amber-900 dark:text-amber-300">
                                {h.leverage_factor}x
                              </span>
                            )}
                            {holdingSignals[h.ticker] && (
                              <span className={`rounded px-1.5 py-0.5 text-xs font-semibold uppercase ${
                                holdingSignals[h.ticker].signal === "buy"
                                  ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
                                  : holdingSignals[h.ticker].signal === "sell"
                                    ? "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300"
                                    : "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400"
                              }`}>
                                {holdingSignals[h.ticker].signal}
                              </span>
                            )}
                          </div>
                          <p className="text-sm text-zinc-400">{h.name}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-6">
                        <div className="text-right">
                          <p className="text-sm text-zinc-500 dark:text-zinc-400">
                            {h.shares} shares @ ${h.avg_cost.toFixed(2)}
                          </p>
                          {h.price !== null && (
                            <p className="font-mono text-base font-semibold dark:text-zinc-200">
                              ${h.market_value!.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                            </p>
                          )}
                        </div>
                        <div className="text-right">
                          {h.pnl !== null && (
                            <>
                              <p className={`font-mono text-base font-semibold ${
                                h.pnl >= 0
                                  ? "text-green-600 dark:text-green-400"
                                  : "text-red-600 dark:text-red-400"
                              }`}>
                                {h.pnl >= 0 ? "+" : ""}${h.pnl.toFixed(2)}
                              </p>
                              <p className={`text-sm ${
                                h.pnl_percent! >= 0
                                  ? "text-green-600 dark:text-green-400"
                                  : "text-red-600 dark:text-red-400"
                              }`}>
                                {h.pnl_percent! >= 0 ? "+" : ""}{h.pnl_percent!.toFixed(2)}%
                              </p>
                            </>
                          )}
                          {h.price === null && (
                            <p className="text-sm text-zinc-400">Price unavailable</p>
                          )}
                        </div>
                        <div className="flex gap-1">
                          <button
                            onClick={() => {
                              setEditingId(h.id);
                              setEditShares(String(h.shares));
                              setEditAvgCost(String(h.avg_cost));
                            }}
                            className="rounded border border-zinc-300 px-2 py-1 text-xs hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-800"
                          >
                            Edit
                          </button>
                          <button
                            onClick={() => deleteHolding(h.id)}
                            className="rounded border border-red-200 px-2 py-1 text-xs text-red-600 hover:bg-red-50 dark:border-red-900 dark:text-red-400 dark:hover:bg-red-950"
                          >
                            Delete
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : portfolio && portfolio.holdings.length === 0 ? (
            /* Empty State */
            <div className="rounded-lg border border-dashed border-zinc-300 p-8 text-center dark:border-zinc-700">
              <p className="text-lg font-medium text-zinc-500 dark:text-zinc-400">
                No holdings yet
              </p>
              <p className="mt-1 text-sm text-zinc-400">
                Add your first holding to start tracking your portfolio.
              </p>
              <button
                onClick={() => setShowAddForm(true)}
                className="mt-4 rounded-lg bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
              >
                + Add Your First Holding
              </button>
            </div>
          ) : null}
        </section>}

        {/* Symbol Catalog */}
        <section className="flex flex-col gap-6">
          <h2 className="text-xl font-semibold dark:text-zinc-200">
            Symbol Catalog
            <span className="ml-2 text-base font-normal text-zinc-400">
              {catalog.length} symbols in database
            </span>
          </h2>
          {[
            { label: "Index ETFs", filter: (s: CatalogSymbol) => s.type === "etf" && s.leverage_factor === 1 },
            { label: "Leveraged ETFs", filter: (s: CatalogSymbol) => s.type === "etf" && s.leverage_factor !== 1 },
            { label: "Stocks", filter: (s: CatalogSymbol) => s.type === "stock" },
          ].map((group) => {
            const items = catalog.filter(group.filter);
            if (items.length === 0) return null;
            return (
              <div key={group.label} className="flex flex-col gap-2">
                <h3 className="text-base font-medium text-zinc-500 dark:text-zinc-400">
                  {group.label}
                </h3>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-5">
                  {items.map((s) => (
              <button
                key={s.ticker}
                onClick={() => selectSymbol(s.ticker)}
                className={`rounded-lg border p-3 text-left transition-colors ${
                  selectedTicker === s.ticker
                    ? "border-blue-500 bg-blue-50 dark:border-blue-400 dark:bg-blue-950"
                    : "border-zinc-200 hover:border-zinc-400 dark:border-zinc-700 dark:hover:border-zinc-500"
                }`}
              >
                <div className="flex items-baseline justify-between">
                  <span className="font-mono font-bold dark:text-white">
                    {s.ticker}
                  </span>
                  {s.leverage_factor !== 1 && (
                    <span className="rounded bg-amber-100 px-1 text-xs font-medium text-amber-700 dark:bg-amber-900 dark:text-amber-300">
                      {s.leverage_factor}x
                    </span>
                  )}
                </div>
                <p className="mt-0.5 truncate text-sm text-zinc-500 dark:text-zinc-400">
                  {s.name}
                </p>
                {s.latest_close && (
                  <p className="mt-1 font-mono text-base font-semibold dark:text-zinc-200">
                    ${s.latest_close.toFixed(2)}
                  </p>
                )}
                <p className="text-xs text-zinc-400">{s.sector}</p>
              </button>
                  ))}
                </div>
              </div>
            );
          })}
        </section>

        {/* Price History Chart */}
        {selectedTicker && (
          <section className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold dark:text-zinc-200">
                {selectedTicker} — Price History
              </h2>
              <div className="flex gap-1">
                {[
                  { label: "3M", days: 90 },
                  { label: "6M", days: 180 },
                  { label: "1Y", days: 365 },
                  { label: "3Y", days: 1095 },
                  { label: "5Y", days: 1825 },
                ].map((opt) => (
                  <button
                    key={opt.label}
                    onClick={() => {
                      setHistoryDays(opt.days);
                      selectSymbol(selectedTicker, opt.days);
                    }}
                    className={`rounded px-3 py-1.5 text-sm font-medium ${
                      historyDays === opt.days
                        ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                        : "text-zinc-500 hover:bg-zinc-200 dark:text-zinc-400 dark:hover:bg-zinc-800"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            {history.length > 0 ? (
              <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-700">
                <Sparkline data={history} />
                <div className="mt-3 flex justify-between text-sm text-zinc-400">
                  <span>{history[0].date}</span>
                  <span>
                    {history.length} trading days ·{" "}
                    Low ${Math.min(...history.map((h) => h.low)).toFixed(2)} ·{" "}
                    High ${Math.max(...history.map((h) => h.high)).toFixed(2)}
                  </span>
                  <span>{history[history.length - 1].date}</span>
                </div>
              </div>
            ) : (
              <p className="text-sm text-zinc-400">Loading...</p>
            )}
          </section>
        )}

        {/* Indicators Panel */}
        {selectedTicker && (
          <section className="flex flex-col gap-4">
            <h2 className="text-xl font-semibold dark:text-zinc-200">
              {selectedTicker} — Technical Indicators
            </h2>

            {indicatorsLoading && (
              <p className="text-sm text-zinc-400">Loading indicators...</p>
            )}

            {indicatorsError && (
              <p className="text-sm text-red-600 dark:text-red-400">{indicatorsError}</p>
            )}

            {indicators && (
              <div className="flex flex-col gap-4">
                {/* Composite Signal */}
                <CompositeCard indicators={indicators} />

                {/* Indicator Cards */}
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  {indicators.indicators.rsi && (
                    <IndicatorCard
                      name="RSI (14)"
                      value={indicators.indicators.rsi.value.toFixed(1)}
                      signal={indicators.composite.directions.rsi ?? "neutral"}
                      detail={
                        indicators.indicators.rsi.signal === "oversold"
                          ? "Below 30 — oversold, may bounce"
                          : indicators.indicators.rsi.signal === "overbought"
                            ? "Above 70 — overbought, may pull back"
                            : "Between 30-70 — neutral momentum"
                      }
                    />
                  )}
                  {indicators.indicators.macd && (
                    <IndicatorCard
                      name="MACD (12/26/9)"
                      value={indicators.indicators.macd.histogram.toFixed(4)}
                      signal={indicators.composite.directions.macd ?? "neutral"}
                      detail={`Line: ${indicators.indicators.macd.macd_line.toFixed(4)} · Signal: ${indicators.indicators.macd.signal_line.toFixed(4)}`}
                    />
                  )}
                  {indicators.indicators.bollinger && (
                    <IndicatorCard
                      name="Bollinger Width"
                      value={(indicators.indicators.bollinger.width * 100).toFixed(2) + "%"}
                      signal={indicators.composite.directions.bollinger ?? "neutral"}
                      detail={`Upper: $${indicators.indicators.bollinger.upper.toFixed(2)} · Lower: $${indicators.indicators.bollinger.lower.toFixed(2)}`}
                    />
                  )}
                  {indicators.indicators.sma_crossover && (
                    <IndicatorCard
                      name="SMA 50/200"
                      value={indicators.indicators.sma_crossover.crossover_type.replace("_", " ")}
                      signal={indicators.composite.directions.sma_crossover ?? "neutral"}
                      detail={`50d: $${indicators.indicators.sma_crossover.sma_50.toFixed(2)} · 200d: $${indicators.indicators.sma_crossover.sma_200.toFixed(2)}${indicators.indicators.sma_crossover.days_since_cross !== null ? ` · ${indicators.indicators.sma_crossover.days_since_cross}d ago` : ""}`}
                    />
                  )}
                  {indicators.indicators.atr && (
                    <IndicatorCard
                      name="ATR (14)"
                      value={"$" + indicators.indicators.atr.value.toFixed(2)}
                      signal={indicators.composite.directions.atr ?? "neutral"}
                      detail={`${indicators.indicators.atr.atr_percent.toFixed(2)}% of price — daily volatility`}
                    />
                  )}
                  {indicators.indicators.beta && (
                    <IndicatorCard
                      name="Beta vs S&P 500"
                      value={indicators.indicators.beta.value.toFixed(2)}
                      signal={indicators.composite.directions.beta ?? "neutral"}
                      detail={indicators.indicators.beta.interpretation}
                    />
                  )}
                  {indicators.indicators.sharpe && (
                    <IndicatorCard
                      name="Sharpe Ratio"
                      value={indicators.indicators.sharpe.value.toFixed(2)}
                      signal={indicators.composite.directions.sharpe ?? "neutral"}
                      detail={`${indicators.indicators.sharpe.interpretation} (rf: ${indicators.indicators.sharpe.risk_free_rate}%)`}
                    />
                  )}
                </div>

                <p className="text-xs text-zinc-400">
                  Computed {indicators.computed_at} · {indicators.data_points} trading days of data
                </p>
              </div>
            )}
          </section>
        )}

        {/* Symbol Lookup */}
        <section className="flex flex-col gap-4">
          <h2 className="text-xl font-semibold dark:text-zinc-200">
            Symbol Lookup
          </h2>
          <div className="flex gap-2">
            <input
              type="text"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              onKeyDown={(e) => e.key === "Enter" && lookupSymbol()}
              placeholder="e.g. QQQ, AAPL"
              className="flex-1 rounded-lg border border-zinc-300 px-4 py-2.5 text-base dark:border-zinc-700 dark:bg-zinc-900 dark:text-white"
            />
            <button
              onClick={lookupSymbol}
              disabled={loading}
              className="rounded-lg bg-zinc-900 px-5 py-2.5 text-base font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
            >
              {loading ? "..." : "Lookup"}
            </button>
            <button
              onClick={searchSymbols}
              className="rounded-lg border border-zinc-300 px-5 py-2.5 text-base font-medium hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
            >
              Search
            </button>
          </div>

          {error && (
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          )}

          {/* Search Results */}
          {searchResults.length > 0 && (
            <div className="rounded-lg border border-zinc-200 dark:border-zinc-700">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-zinc-200 text-left text-zinc-500 dark:border-zinc-700 dark:text-zinc-400">
                    <th className="px-4 py-2">Symbol</th>
                    <th className="px-4 py-2">Name</th>
                    <th className="px-4 py-2">Type</th>
                  </tr>
                </thead>
                <tbody>
                  {searchResults.map((r) => (
                    <tr
                      key={r.symbol}
                      className="border-b border-zinc-100 cursor-pointer hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-900"
                      onClick={() => {
                        setSymbol(r.symbol);
                        setSearchResults([]);
                      }}
                    >
                      <td className="px-4 py-2 font-mono font-medium dark:text-white">
                        {r.symbol}
                      </td>
                      <td className="px-4 py-2 dark:text-zinc-300">
                        {r.name}
                      </td>
                      <td className="px-4 py-2 dark:text-zinc-400">
                        {r.type}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Quote Card */}
          {quote && (
            <div className="rounded-lg border border-zinc-200 p-5 dark:border-zinc-700">
              <div className="flex items-baseline justify-between">
                <span className="text-2xl font-bold font-mono dark:text-white">
                  {quote.symbol}
                </span>
                <span className="text-2xl font-semibold dark:text-white">
                  ${quote.price.toFixed(2)}
                </span>
              </div>
              <div className="mt-1 flex items-baseline justify-between">
                {sector && (
                  <span className="text-sm text-zinc-500 dark:text-zinc-400">
                    {sector.sector} · {sector.industry}
                    {sector.is_etf && (
                      <span className="ml-2 rounded bg-blue-100 px-1.5 py-0.5 text-xs text-blue-700 dark:bg-blue-900 dark:text-blue-300">
                        ETF
                      </span>
                    )}
                  </span>
                )}
                <span
                  className={`text-sm font-medium ${
                    quote.change >= 0
                      ? "text-green-600 dark:text-green-400"
                      : "text-red-600 dark:text-red-400"
                  }`}
                >
                  {quote.change >= 0 ? "+" : ""}
                  {quote.change.toFixed(2)} ({quote.change_percent.toFixed(2)}%)
                </span>
              </div>
            </div>
          )}
        </section>

        {/* Macro Snapshot */}
        <section className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold dark:text-zinc-200">
              Macro Indicators
            </h2>
            <button
              onClick={loadMacro}
              className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm font-medium hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
            >
              Load
            </button>
          </div>

          {macro && (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
              {[
                { label: "Fed Funds Rate", value: macro.fed_funds_rate, suffix: "%" },
                { label: "VIX", value: macro.vix, suffix: "" },
                { label: "3M Treasury", value: macro.treasury_3mo, suffix: "%" },
                { label: "2Y Treasury", value: macro.treasury_2y, suffix: "%" },
                { label: "10Y Treasury", value: macro.treasury_10y, suffix: "%" },
                { label: "30Y Treasury", value: macro.treasury_30y, suffix: "%" },
              ].map((item) => (
                <div
                  key={item.label}
                  className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700"
                >
                  <p className="text-sm text-zinc-500 dark:text-zinc-400">
                    {item.label}
                  </p>
                  <p className="text-xl font-semibold font-mono dark:text-white">
                    {item.value !== null ? `${item.value}${item.suffix}` : "—"}
                  </p>
                </div>
              ))}
              <p className="col-span-full text-xs text-zinc-400">
                As of {macro.as_of}
              </p>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
