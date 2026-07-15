"use client";

import { useState } from "react";
import type { StressScenario } from "@/types";

export function StressScenarioCard({ scenario }: { scenario: StressScenario }) {
  const [expanded, setExpanded] = useState(false);
  const isPositive = scenario.portfolio_impact_pct >= 0;
  return (
    <div className={`rounded-lg border p-4 ${
      isPositive
        ? "border-green-200 dark:border-green-800"
        : scenario.portfolio_impact_pct < -20
          ? "border-red-300 dark:border-red-700"
          : "border-zinc-200 dark:border-zinc-700"
    }`}>
      <button onClick={() => setExpanded(!expanded)} className="w-full text-left">
        <p className="text-sm font-medium text-zinc-600 dark:text-zinc-300">{scenario.scenario_name}</p>
        <p className={`font-mono text-xl font-semibold ${
          isPositive ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"
        }`}>
          {isPositive ? "+" : ""}{scenario.portfolio_impact_pct.toFixed(1)}%
        </p>
        <p className={`text-sm ${
          isPositive ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"
        }`}>
          {isPositive ? "+" : ""}${scenario.portfolio_impact_dollar.toLocaleString(undefined, { maximumFractionDigits: 0 })}
        </p>
        <p className="mt-1 text-xs text-zinc-400">{scenario.period} {expanded ? "▲" : "▼"}</p>
      </button>
      {expanded && scenario.holdings_impact.length > 0 && (
        <div className="mt-3 border-t border-inherit pt-3">
          <div className="flex flex-col gap-1">
            {scenario.holdings_impact.map((h) => (
              <div key={h.ticker} className="flex justify-between text-xs">
                <span className="font-mono text-zinc-600 dark:text-zinc-300">{h.ticker}</span>
                {h.return_pct !== null ? (
                  <span className={h.return_pct >= 0 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}>
                    {h.return_pct >= 0 ? "+" : ""}{h.return_pct.toFixed(1)}%
                  </span>
                ) : (
                  <span className="text-zinc-400">{h.note ?? "no data"}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
