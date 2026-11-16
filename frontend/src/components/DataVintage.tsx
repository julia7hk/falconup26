import type { IndicatorData } from "@/types";

/**
 * Footer line under an indicator panel reporting how old the underlying price
 * data is. Shared by the dashboard and the symbol-detail page so the two can't
 * disagree about freshness.
 *
 * This exists because "Computed <today>" on its own is misleading: the math
 * runs today regardless of whether its inputs stopped updating months ago. A
 * timing tool that silently serves a stale chart is worse than one that admits
 * it, so when the backend flags `stale` we say so in plain language instead of
 * burying it in a date the reader has to subtract for themselves.
 */
export default function DataVintage({ indicators }: { indicators: IndicatorData }) {
  const { computed_at, data_through, data_age_days, stale, data_points } = indicators;

  if (stale) {
    return (
      <p className="text-xs text-amber-500">
        ⚠ Price data is {data_age_days} days behind — latest bar is {data_through}.
        These signals describe the market as of that date, not today.
      </p>
    );
  }

  return (
    <p className="text-xs text-zinc-400">
      Computed {computed_at} · data through {data_through} · {data_points} trading
      days of data
    </p>
  );
}
