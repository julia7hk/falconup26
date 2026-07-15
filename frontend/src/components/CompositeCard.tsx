"use client";

import { useState } from "react";
import type { IndicatorData } from "@/types";

export function CompositeCard({ indicators }: { indicators: IndicatorData }) {
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
