"use client";

import { useState } from "react";
import type { RiskExplainResponse, RiskExplanation } from "@/types";

// Severity → chip styling. Ordered to read at a glance: green (fine) through
// red (biggest risks). Mirrors the harsh, conservative grade thresholds.
const SEVERITY_STYLES: Record<string, string> = {
  none: "text-zinc-500 bg-zinc-100 dark:text-zinc-400 dark:bg-zinc-800",
  low: "text-green-700 bg-green-100 dark:text-green-300 dark:bg-green-950",
  moderate: "text-amber-700 bg-amber-100 dark:text-amber-300 dark:bg-amber-950",
  high: "text-orange-700 bg-orange-100 dark:text-orange-300 dark:bg-orange-950",
  severe: "text-red-700 bg-red-100 dark:text-red-300 dark:bg-red-950",
};

/**
 * Plain-English "why this grade" surface for the portfolio risk card.
 *
 * Presentation only — the backend owns all explanation content. The `explanation`
 * prop is the deterministic copy folded into GET /api/portfolio/risk, so the
 * card renders instantly. On first expand it lazily fetches
 * GET /api/portfolio/risk/explain, which may return an LLM-enriched rephrasing
 * (M8 PR2); if that succeeds it swaps in, otherwise the deterministic prop stands.
 * The upgrade is silent — the same grade and figures either way. Collapsed by
 * default so it doesn't crowd the grade; the disclaimer shows once expanded.
 */
export function RiskExplainCard({ explanation }: { explanation: RiskExplanation }) {
  const [expanded, setExpanded] = useState(false);
  const [enriched, setEnriched] = useState<RiskExplanation | null>(null);
  const [fetched, setFetched] = useState(false);

  // Fetch the (possibly LLM-enriched) explanation once, on first expand.
  async function handleToggle() {
    const next = !expanded;
    setExpanded(next);
    if (!next || fetched) return;
    setFetched(true); // mark before awaiting so we never double-fetch
    try {
      const res = await fetch("/api/portfolio/risk/explain", {
        credentials: "include",
      });
      if (!res.ok) return;
      const data: RiskExplainResponse = await res.json();
      if (data.available && data.explanation) setEnriched(data.explanation);
    } catch {
      // Network error — keep the deterministic prop; nothing to surface.
    }
  }

  const shown = enriched ?? explanation;

  return (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-700">
      <button
        onClick={handleToggle}
        className="flex w-full items-center justify-between gap-3 p-4 text-left"
      >
        <div>
          <p className="text-sm font-medium text-zinc-700 dark:text-zinc-200">
            Why this grade?
          </p>
          <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">
            {shown.headline}
          </p>
        </div>
        <span className="shrink-0 text-xs text-zinc-400">{expanded ? "▲" : "▼"}</span>
      </button>

      {expanded && (
        <div className="border-t border-zinc-200 px-4 pb-4 pt-3 dark:border-zinc-700">
          <p className="text-sm text-zinc-600 dark:text-zinc-300">{shown.overview}</p>

          <div className="mt-4 flex flex-col gap-4">
            {shown.components.map((c) => (
              <div key={c.key}>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-zinc-700 dark:text-zinc-200">
                    {c.label}
                  </span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${
                      SEVERITY_STYLES[c.severity] ?? SEVERITY_STYLES.none
                    }`}
                  >
                    {c.severity}
                  </span>
                  <span className="ml-auto font-mono text-xs text-zinc-400">
                    -{c.penalty}/{c.max_penalty}
                  </span>
                </div>
                <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">{c.meaning}</p>
                <p className="mt-1 text-xs text-zinc-600 dark:text-zinc-300">{c.detail}</p>
              </div>
            ))}
          </div>

          <p className="mt-4 border-t border-zinc-100 pt-3 text-[11px] italic text-zinc-400 dark:border-zinc-800">
            {shown.disclaimer}
          </p>
        </div>
      )}
    </div>
  );
}
