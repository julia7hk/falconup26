const SIGNAL_COLORS: Record<string, string> = {
  bullish: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  oversold: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  low_volatility: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  bearish: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
  overbought: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
  high_volatility: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
  neutral: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400",
};

export function SignalBadge({ signal }: { signal: string }) {
  return (
    <span
      className={`rounded px-1.5 py-0.5 text-xs font-medium ${SIGNAL_COLORS[signal] ?? SIGNAL_COLORS.neutral}`}
    >
      {signal.replace("_", " ")}
    </span>
  );
}
