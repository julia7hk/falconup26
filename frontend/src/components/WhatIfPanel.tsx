"use client";

import { useState } from "react";
import type { Holding, WhatIfResponse, WhatIfDiffEntry } from "@/types";
import { RiskGradeCard } from "./RiskGradeCard";

const inputCls =
  "w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-white";
const labelCls = "block text-sm text-zinc-500 dark:text-zinc-400";
const btnCls =
  "rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300";

// How to label and format each diffed metric. Keyed to the backend diff keys.
const METRIC_FORMAT: Record<string, { label: string; fmt: (v: number) => string }> = {
  concentration: { label: "Concentration (HHI)", fmt: (v) => v.toFixed(3) },
  effective_leverage: { label: "Effective Leverage", fmt: (v) => `${v.toFixed(2)}x` },
  portfolio_beta: { label: "Portfolio Beta", fmt: (v) => v.toFixed(2) },
  max_drawdown: { label: "Max Drawdown", fmt: (v) => `-${v.toFixed(1)}%` },
  risk_grade: { label: "Risk Grade (score)", fmt: (v) => v.toFixed(0) },
};
const METRIC_ORDER = [
  "risk_grade",
  "concentration",
  "effective_leverage",
  "portfolio_beta",
  "max_drawdown",
];

const DIRECTION_STYLE: Record<WhatIfDiffEntry["direction"], { arrow: string; cls: string }> = {
  improved: { arrow: "▼ better", cls: "text-green-600 dark:text-green-400" },
  worsened: { arrow: "▲ worse", cls: "text-red-600 dark:text-red-400" },
  unchanged: { arrow: "— same", cls: "text-zinc-400" },
  unavailable: { arrow: "n/a", cls: "text-zinc-400" },
};

function DiffRow({ metricKey, entry }: { metricKey: string; entry: WhatIfDiffEntry }) {
  const meta = METRIC_FORMAT[metricKey];
  if (!meta) return null;
  const style = DIRECTION_STYLE[entry.direction];

  // Risk grade reads better as a letter; the rest as their formatted scalar.
  const isGrade = metricKey === "risk_grade";
  const before =
    entry.before === null
      ? "—"
      : isGrade
        ? `${entry.before_grade ?? "?"} (${meta.fmt(entry.before)})`
        : meta.fmt(entry.before);
  const after =
    entry.after === null
      ? "—"
      : isGrade
        ? `${entry.after_grade ?? "?"} (${meta.fmt(entry.after)})`
        : meta.fmt(entry.after);

  return (
    <div className="flex items-center gap-2 border-b border-zinc-100 py-2 text-sm last:border-0 dark:border-zinc-800">
      <span className="flex-1 text-zinc-600 dark:text-zinc-300">{meta.label}</span>
      <span className="w-28 text-right font-mono text-zinc-500 dark:text-zinc-400">{before}</span>
      <span className="w-6 text-center text-zinc-400">→</span>
      <span className="w-28 text-right font-mono text-zinc-700 dark:text-zinc-200">{after}</span>
      <span className={`w-20 text-right text-xs font-semibold ${style.cls}`}>{style.arrow}</span>
    </div>
  );
}

/**
 * What-if simulator: pick a hypothetical buy/sell, see how the portfolio's
 * risk metrics would change. Calls POST /api/portfolio/what-if — a pure
 * simulation that never touches the real portfolio.
 */
export function WhatIfPanel({ holdings }: { holdings: Holding[] }) {
  const [open, setOpen] = useState(false);
  const [ticker, setTicker] = useState("");
  const [action, setAction] = useState<"buy" | "sell">("buy");
  const [quantity, setQuantity] = useState("");
  const [result, setResult] = useState<WhatIfResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function run() {
    const qty = parseFloat(quantity);
    if (!ticker.trim() || isNaN(qty) || qty <= 0) {
      setError("Enter a symbol and a positive quantity.");
      return;
    }
    setError("");
    setLoading(true);
    setResult(null);
    try {
      const res = await fetch("/api/portfolio/what-if", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker: ticker.toUpperCase(), action, quantity: qty }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Failed (${res.status})`);
      }
      setResult(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Simulation failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-700">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between p-4 text-left"
      >
        <div>
          <p className="text-sm font-medium dark:text-zinc-200">What-If Analysis</p>
          <p className="text-xs text-zinc-400">
            Simulate a trade and see how your risk would change — nothing is saved.
          </p>
        </div>
        <span className="text-zinc-400">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="border-t border-zinc-200 p-4 dark:border-zinc-700">
          {/* Trade form */}
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="flex-1">
              <label className={labelCls}>Symbol</label>
              <input
                type="text"
                list="whatif-tickers"
                value={ticker}
                onChange={(e) => setTicker(e.target.value.toUpperCase())}
                placeholder="e.g. QQQ"
                className={inputCls}
              />
              <datalist id="whatif-tickers">
                {holdings.map((h) => (
                  <option key={h.ticker} value={h.ticker} />
                ))}
              </datalist>
            </div>
            <div className="flex-1">
              <label className={labelCls}>Action</label>
              <div className="flex gap-1 rounded-lg border border-zinc-300 p-1 dark:border-zinc-700">
                {(["buy", "sell"] as const).map((a) => (
                  <button
                    key={a}
                    type="button"
                    onClick={() => setAction(a)}
                    className={`flex-1 rounded-md px-3 py-1.5 text-sm font-medium capitalize ${
                      action === a
                        ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                        : "text-zinc-500 dark:text-zinc-400"
                    }`}
                  >
                    {a}
                  </button>
                ))}
              </div>
            </div>
            <div className="flex-1">
              <label className={labelCls}>Shares</label>
              <input
                type="number"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                placeholder="10"
                min="0"
                step="any"
                className={inputCls}
              />
            </div>
            <button onClick={run} disabled={loading} className={btnCls}>
              {loading ? "Simulating..." : "Simulate"}
            </button>
          </div>

          {error && <p className="mt-2 text-sm text-red-600 dark:text-red-400">{error}</p>}

          {/* Result */}
          {result && (
            <div className="mt-5 flex flex-col gap-4">
              <p className="text-sm text-zinc-600 dark:text-zinc-300">
                If you{" "}
                <span className="font-semibold capitalize">{result.trade.action}</span>{" "}
                <span className="font-semibold">{result.trade.quantity}</span> share
                {result.trade.quantity !== 1 ? "s" : ""} of{" "}
                <span className="font-semibold">{result.trade.ticker}</span>:
              </p>

              {/* Per-metric diff */}
              <div className="rounded-lg border border-zinc-200 px-4 py-1 dark:border-zinc-700">
                <div className="flex items-center gap-2 border-b border-zinc-200 py-2 text-xs font-medium uppercase tracking-wide text-zinc-400 dark:border-zinc-700">
                  <span className="flex-1">Metric</span>
                  <span className="w-28 text-right">Now</span>
                  <span className="w-6" />
                  <span className="w-28 text-right">After</span>
                  <span className="w-20 text-right">Change</span>
                </div>
                {METRIC_ORDER.map((key) =>
                  result.diff[key] ? (
                    <DiffRow key={key} metricKey={key} entry={result.diff[key]} />
                  ) : null,
                )}
              </div>

              {/* Before/after grade cards */}
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  <p className="mb-1 text-xs font-medium uppercase tracking-wide text-zinc-400">
                    Now
                  </p>
                  {result.before.risk_grade ? (
                    <RiskGradeCard grade={result.before.risk_grade} />
                  ) : (
                    <p className="rounded-lg border border-zinc-200 p-4 text-sm text-zinc-400 dark:border-zinc-700">
                      Grade unavailable (not enough history).
                    </p>
                  )}
                </div>
                <div>
                  <p className="mb-1 text-xs font-medium uppercase tracking-wide text-zinc-400">
                    After trade
                  </p>
                  {result.after.risk_grade ? (
                    <RiskGradeCard grade={result.after.risk_grade} />
                  ) : (
                    <p className="rounded-lg border border-zinc-200 p-4 text-sm text-zinc-400 dark:border-zinc-700">
                      Grade unavailable (not enough history).
                    </p>
                  )}
                </div>
              </div>

              {result.notes.length > 0 && (
                <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-950/40">
                  {result.notes.map((note, i) => (
                    <p key={i} className="text-xs text-amber-700 dark:text-amber-300">
                      ⚠ {note}
                    </p>
                  ))}
                </div>
              )}

              <p className="text-xs text-zinc-400">{result.disclaimer}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
