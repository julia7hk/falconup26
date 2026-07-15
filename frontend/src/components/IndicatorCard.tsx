import { SignalBadge } from "./SignalBadge";

export function IndicatorCard({
  name,
  value,
  signal,
  detail,
}: {
  name: string;
  value: string;
  signal: string;
  detail: string;
}) {
  return (
    <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-zinc-500 dark:text-zinc-400">
          {name}
        </p>
        <SignalBadge signal={signal} />
      </div>
      <p className="mt-1 font-mono text-lg font-semibold dark:text-white">
        {value}
      </p>
      <p className="mt-0.5 text-xs text-zinc-400">{detail}</p>
    </div>
  );
}
