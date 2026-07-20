import type { IndicatorData } from "@/types";

const INDICATOR_LABELS: Record<string, string> = {
  rsi: "RSI",
  macd: "MACD",
  bollinger: "Bollinger",
  sma_crossover: "SMA 50/200",
  atr: "ATR",
  beta: "Beta",
  sharpe: "Sharpe",
  sortino: "Sortino",
  max_drawdown: "Max Drawdown",
};

/**
 * Symbol-level "why" behind a composite Buy/Hold/Sell signal. Shared by the
 * symbol-detail CompositeCard and the per-holding dropdown so the explanation
 * stays consistent everywhere. Pure presentation of already-computed data —
 * no personalization (see HoldingSignalPanel for that).
 */
export function SignalBreakdown({
  composite,
}: {
  composite: IndicatorData["composite"];
}) {
  const directions = Object.values(composite.directions);
  const bullishCount = directions.filter((d) => d === "bullish").length;
  const bearishCount = directions.filter((d) => d === "bearish").length;
  const neutralCount = directions.filter((d) => d === "neutral").length;

  // Sort indicators by how hard they push the composite (|contribution|), biggest first.
  const rows = Object.entries(composite.contributions)
    .map(([key, contribution]) => ({
      key,
      label: INDICATOR_LABELS[key] ?? key,
      contribution,
      direction: composite.directions[key] ?? "neutral",
    }))
    .sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution));

  const maxAbs = Math.max(...rows.map((r) => Math.abs(r.contribution)), 0.0001);

  return (
    <div className="space-y-3 text-sm leading-relaxed text-zinc-600 dark:text-zinc-300">
      <p>
        This signal combines all {rows.length} indicators into one recommendation using a
        weighted average. Each indicator is scored from -1 (bearish) to +1 (bullish), then
        multiplied by its weight. The composite score ({composite.score > 0 ? "+" : ""}
        {composite.score.toFixed(3)}) is that weighted average.
        {composite.signal === "buy"
          ? " A score above +0.15 triggers a Buy signal."
          : composite.signal === "sell"
            ? " A score below -0.15 triggers a Sell signal."
            : " A score between -0.15 and +0.15 means Hold — no strong direction."}
      </p>
      <p>
        Right now, {bullishCount} indicator{bullishCount !== 1 ? "s" : ""}{" "}
        {bullishCount !== 1 ? "are" : "is"} bullish, {bearishCount}{" "}
        {bearishCount !== 1 ? "are" : "is"} bearish
        {neutralCount > 0
          ? `, and ${neutralCount} ${neutralCount !== 1 ? "are" : "is"} neutral`
          : ""}
        . Confidence ({(composite.confidence * 100).toFixed(0)}%) reflects how strongly they
        agree —
        {composite.confidence < 0.3
          ? " it's low because the indicators are giving mixed signals."
          : composite.confidence < 0.6
            ? " it's moderate: most lean the same way but there's some disagreement."
            : " it's high: the indicators mostly agree."}
      </p>

      {/* Per-indicator contribution breakdown — which indicators drive the score, and how hard */}
      <div className="space-y-1.5">
        <p className="text-xs font-medium uppercase tracking-wide text-zinc-400">
          What&apos;s driving it
        </p>
        {rows.map((r) => (
          <div key={r.key} className="flex items-center gap-2">
            <span className="w-24 shrink-0 text-xs text-zinc-500 dark:text-zinc-400">
              {r.label}
            </span>
            <div className="relative h-2 flex-1 rounded bg-zinc-200 dark:bg-zinc-800">
              <div
                className={`absolute top-0 left-0 h-2 rounded ${
                  r.direction === "bullish"
                    ? "bg-green-500"
                    : r.direction === "bearish"
                      ? "bg-red-500"
                      : "bg-zinc-400"
                }`}
                style={{ width: `${(Math.abs(r.contribution) / maxAbs) * 100}%` }}
              />
            </div>
            <span
              className={`w-14 shrink-0 text-right font-mono text-xs ${
                r.direction === "bullish"
                  ? "text-green-600 dark:text-green-400"
                  : r.direction === "bearish"
                    ? "text-red-600 dark:text-red-400"
                    : "text-zinc-500"
              }`}
            >
              {r.contribution > 0 ? "+" : ""}
              {r.contribution.toFixed(3)}
            </span>
          </div>
        ))}
      </div>

      <p className="text-xs text-zinc-400">
        Weights: RSI 13% · MACD 13% · Bollinger 8% · SMA 13% · ATR 8% · Beta 13% · Sharpe 12%
        · Sortino 12% · Max Drawdown 8%
      </p>
    </div>
  );
}
