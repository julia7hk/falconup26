"use client";

import { useState } from "react";
import type { IndicatorData } from "@/types";
import { SignalBreakdown } from "./SignalBreakdown";

export function CompositeCard({ indicators }: { indicators: IndicatorData }) {
  const [expanded, setExpanded] = useState(false);
  const { composite } = indicators;

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
          <SignalBreakdown composite={composite} />
        </div>
      )}
    </div>
  );
}
