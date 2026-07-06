"use client";

import { useEffect, useState } from "react";

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

export default function Home() {
  const [catalog, setCatalog] = useState<CatalogSymbol[]>([]);
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [history, setHistory] = useState<PriceBar[]>([]);
  const [historyDays, setHistoryDays] = useState(365);
  const [symbol, setSymbol] = useState("");
  const [quote, setQuote] = useState<Quote | null>(null);
  const [sector, setSector] = useState<SectorInfo | null>(null);
  const [macro, setMacro] = useState<MacroSnapshot | null>(null);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetch("/api/symbols/catalog")
      .then((res) => res.json())
      .then(setCatalog)
      .catch(() => {});
  }, []);

  async function selectSymbol(ticker: string, days = historyDays) {
    setSelectedTicker(ticker);
    setHistory([]);
    try {
      const res = await fetch(
        `/api/symbols/${ticker}/history-db?days=${days}`
      );
      if (res.ok) setHistory(await res.json());
    } catch {}
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
        <h1 className="text-4xl font-bold tracking-tight dark:text-white">
          FalconUp
        </h1>

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
