"use client";

import { useEffect, useState } from "react";
import { authClient } from "@/lib/auth-client";
import { useRouter } from "next/navigation";
import type {
  CatalogSymbol,
  PriceBar,
  Quote,
  SectorInfo,
  MacroSnapshot,
  SearchResult,
  IndicatorData,
} from "@/types";
import { Sparkline } from "@/components/Sparkline";
import { IndicatorCard } from "@/components/IndicatorCard";
import { CompositeCard } from "@/components/CompositeCard";

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

  useEffect(() => {
    fetch("/api/symbols/catalog")
      .then((res) => res.json())
      .then(setCatalog)
      .catch(() => {});
  }, []);

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
      <main className="flex flex-1 w-full max-w-6xl flex-col gap-10 py-8 px-4 sm:py-12 sm:px-8">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold tracking-tight dark:text-white sm:text-4xl">
            FalconUp
          </h1>
          {session ? (
            <div className="flex items-center gap-3">
              <a
                href="/dashboard"
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
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
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
                <div className="mt-3 flex flex-col gap-1 text-sm text-zinc-400 sm:flex-row sm:justify-between">
                  <span>{history[0].date} — {history[history.length - 1].date}</span>
                  <span>
                    {history.length} days · Low ${Math.min(...history.map((h) => h.low)).toFixed(2)} · High ${Math.max(...history.map((h) => h.high)).toFixed(2)}
                  </span>
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
          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              type="text"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              onKeyDown={(e) => e.key === "Enter" && lookupSymbol()}
              placeholder="e.g. QQQ, AAPL"
              className="w-full rounded-lg border border-zinc-300 px-4 py-2.5 text-base dark:border-zinc-700 dark:bg-zinc-900 dark:text-white sm:flex-1"
            />
            <div className="flex gap-2">
              <button
                onClick={lookupSymbol}
                disabled={loading}
                className="flex-1 rounded-lg bg-zinc-900 px-5 py-2.5 text-base font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300 sm:flex-none"
              >
                {loading ? "..." : "Lookup"}
              </button>
              <button
                onClick={searchSymbols}
                className="flex-1 rounded-lg border border-zinc-300 px-5 py-2.5 text-base font-medium hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800 sm:flex-none"
              >
                Search
              </button>
            </div>
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
