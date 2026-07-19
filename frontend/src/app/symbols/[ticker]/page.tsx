"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import type { PriceBar, IndicatorData } from "@/types";
import { PriceChart } from "@/components/PriceChart";
import { IndicatorCard } from "@/components/IndicatorCard";
import { CompositeCard } from "@/components/CompositeCard";

export default function SymbolPage() {
  const { ticker } = useParams<{ ticker: string }>();
  const upperTicker = ticker.toUpperCase();

  const [history, setHistory] = useState<PriceBar[]>([]);
  const [historyDays, setHistoryDays] = useState(365);
  const [indicators, setIndicators] = useState<IndicatorData | null>(null);
  const [indicatorsError, setIndicatorsError] = useState("");
  // Track what params were last fetched to derive loading state
  const [fetched, setFetched] = useState<{ ticker: string; days: number } | null>(null);
  const indicatorsLoading = !fetched || fetched.ticker !== upperTicker || fetched.days !== historyDays;
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    async function load() {
      try {
        const [histRes, indRes] = await Promise.all([
          fetch(`/api/symbols/${upperTicker}/history-db?days=${historyDays}`, { signal: ctrl.signal }),
          fetch(`/api/symbols/${upperTicker}/indicators`, { signal: ctrl.signal }),
        ]);
        if (ctrl.signal.aborted) return;
        if (histRes.ok) setHistory(await histRes.json());
        if (indRes.ok) {
          setIndicators(await indRes.json());
          setIndicatorsError("");
        } else {
          setIndicatorsError(`Could not load indicators (${indRes.status})`);
        }
      } catch (e) {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setIndicatorsError("Failed to fetch data");
      } finally {
        if (!ctrl.signal.aborted) setFetched({ ticker: upperTicker, days: historyDays });
      }
    }

    load();

    return () => ctrl.abort();
  }, [upperTicker, historyDays]);

  function changeRange(days: number) {
    setHistoryDays(days);
  }

  return (
    <div className="flex flex-col flex-1 items-center bg-zinc-50 font-sans dark:bg-zinc-950">
      <main className="flex flex-1 w-full max-w-6xl flex-col gap-8 py-8 px-4 sm:py-12 sm:px-8">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold tracking-tight dark:text-white sm:text-4xl">
            <span className="font-mono">{upperTicker}</span>
          </h1>
          <Link
            href="/"
            className="text-sm text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200"
          >
            ← Back to Market
          </Link>
        </div>

        {/* Price History Chart */}
        <section className="flex flex-col gap-4">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <h2 className="text-xl font-semibold dark:text-zinc-200">Price History</h2>
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
                  onClick={() => changeRange(opt.days)}
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
              <PriceChart data={history} />
              <div className="mt-3 flex flex-col gap-1 text-sm text-zinc-400 sm:flex-row sm:justify-between">
                <span>
                  {history[0].date} — {history[history.length - 1].date}
                </span>
                <span>
                  {history.length} days · Low $
                  {Math.min(...history.map((h) => h.low)).toFixed(2)} · High $
                  {Math.max(...history.map((h) => h.high)).toFixed(2)}
                </span>
              </div>
            </div>
          ) : (
            <p className="text-sm text-zinc-400">Loading...</p>
          )}
        </section>

        {/* Technical Indicators */}
        <section className="flex flex-col gap-4">
          <h2 className="text-xl font-semibold dark:text-zinc-200">Technical Indicators</h2>

          {indicatorsLoading && (
            <p className="text-sm text-zinc-400">Loading indicators...</p>
          )}

          {indicatorsError && (
            <p className="text-sm text-red-600 dark:text-red-400">{indicatorsError}</p>
          )}

          {indicators && (
            <div className="flex flex-col gap-4">
              <CompositeCard indicators={indicators} />

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
                {indicators.indicators.sortino && (
                  <IndicatorCard
                    name="Sortino Ratio"
                    value={indicators.indicators.sortino.value.toFixed(2)}
                    signal={indicators.composite.directions.sortino ?? "neutral"}
                    detail={`${indicators.indicators.sortino.interpretation} — penalizes only downside volatility`}
                  />
                )}
                {indicators.indicators.max_drawdown && (
                  <IndicatorCard
                    name="Max Drawdown"
                    value={`-${indicators.indicators.max_drawdown.value.toFixed(1)}%`}
                    signal={indicators.composite.directions.max_drawdown ?? "neutral"}
                    detail={`Worst peak-to-trough: ${indicators.indicators.max_drawdown.peak_date} → ${indicators.indicators.max_drawdown.trough_date}`}
                  />
                )}
              </div>

              <p className="text-xs text-zinc-400">
                Computed {indicators.computed_at} · {indicators.data_points} trading days of data
              </p>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
