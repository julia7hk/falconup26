import type { Holding, IndicatorData } from "@/types";
import { SignalBreakdown } from "./SignalBreakdown";

/**
 * Expanded dropdown body for a single holding: the symbol-level "why"
 * (SignalBreakdown) framed against *this user's* position — avg cost vs.
 * current price, unrealized P&L, and weight in the portfolio.
 *
 * The personalized text is deterministic context, never a second
 * recommendation: the composite signal is symbol-level and identical for
 * everyone; only the framing here is the user's. (Precursor to the M8
 * deterministic explainer, which will formalize these templates backend-side.)
 */
export function HoldingSignalPanel({
  holding,
  indicators,
  totalValue,
}: {
  holding: Holding;
  indicators: IndicatorData;
  totalValue: number;
}) {
  const { composite } = indicators;
  const signalLabel =
    composite.signal === "buy" ? "Buy" : composite.signal === "sell" ? "Sell" : "Hold";

  const weight =
    holding.market_value !== null && totalValue > 0
      ? (holding.market_value / totalValue) * 100
      : null;

  return (
    <div className="mt-3 space-y-4 border-t border-zinc-200 pt-3 dark:border-zinc-700">
      {/* Your position — personalized context */}
      <div className="space-y-1.5">
        <p className="text-xs font-medium uppercase tracking-wide text-zinc-400">
          Your position
        </p>
        <p className="text-sm leading-relaxed text-zinc-600 dark:text-zinc-300">
          {holding.pnl_percent !== null ? (
            <>
              You&apos;re{" "}
              <span
                className={
                  holding.pnl_percent >= 0
                    ? "font-semibold text-green-600 dark:text-green-400"
                    : "font-semibold text-red-600 dark:text-red-400"
                }
              >
                {holding.pnl_percent >= 0 ? "up" : "down"}{" "}
                {Math.abs(holding.pnl_percent).toFixed(1)}%
              </span>{" "}
              on this position (avg ${holding.avg_cost.toFixed(2)}
              {holding.price !== null ? ` → $${holding.price.toFixed(2)}` : ""}).
            </>
          ) : (
            <>Avg cost ${holding.avg_cost.toFixed(2)} — current price unavailable.</>
          )}
          {weight !== null && (
            <>
              {" "}It&apos;s{" "}
              <span className="font-semibold">{weight.toFixed(1)}%</span> of your portfolio
              {weight >= 25 ? " — a large single-name concentration." : "."}
            </>
          )}
        </p>
        <p className="text-xs leading-relaxed text-zinc-500 dark:text-zinc-400">
          The <span className="font-medium">{signalLabel}</span> signal reflects{" "}
          {holding.ticker}&apos;s indicators only — it doesn&apos;t account for your entry price or
          how much you hold. Read it alongside your position above, not on its own. This is
          educational analysis, not financial advice.
        </p>
      </div>

      {/* Why — symbol-level breakdown (shared with the symbol-detail card) */}
      <SignalBreakdown composite={composite} />
    </div>
  );
}
