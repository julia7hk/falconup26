import type { RiskData } from "@/types";

export function LeverageGauge({ data }: { data: NonNullable<RiskData["effective_leverage"]> }) {
  // Semi-circular gauge from 1x to 5x
  const minVal = 1, maxVal = 5;
  const clamped = Math.max(minVal, Math.min(maxVal, data.value));
  const pct = (clamped - minVal) / (maxVal - minVal);
  const angle = Math.PI * (1 - pct); // left (PI) = 1x, right (0) = 5x

  const cx = 100, cy = 90, r = 70;
  const needleX = cx + r * 0.85 * Math.cos(angle);
  const needleY = cy - r * 0.85 * Math.sin(angle);

  // Color zones
  const zones = [
    { start: 0, end: 0.125, color: "#22c55e" },     // 1x-1.5x green
    { start: 0.125, end: 0.375, color: "#f59e0b" },  // 1.5x-2.5x amber
    { start: 0.375, end: 0.625, color: "#f97316" },   // 2.5x-3.5x orange
    { start: 0.625, end: 1, color: "#ef4444" },       // 3.5x-5x red
  ];

  return (
    <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-700">
      <p className="text-sm font-medium text-zinc-500 dark:text-zinc-400">Effective Leverage</p>
      <div className="mt-2 flex justify-center">
        <svg viewBox="0 0 200 110" className="h-28 w-44">
          {/* Arc zones */}
          {zones.map((z, i) => {
            const startAngle = Math.PI * (1 - z.start);
            const endAngle = Math.PI * (1 - z.end);
            const x1 = cx + r * Math.cos(startAngle);
            const y1 = cy - r * Math.sin(startAngle);
            const x2 = cx + r * Math.cos(endAngle);
            const y2 = cy - r * Math.sin(endAngle);
            return (
              <path
                key={i}
                d={`M ${x1} ${y1} A ${r} ${r} 0 0 1 ${x2} ${y2}`}
                fill="none"
                stroke={z.color}
                strokeWidth="12"
                strokeLinecap="round"
                opacity={0.3}
              />
            );
          })}
          {/* Needle */}
          <line x1={cx} y1={cy} x2={needleX} y2={needleY} stroke="#18181b" strokeWidth="2.5" className="dark:stroke-zinc-300" />
          <circle cx={cx} cy={cy} r="4" fill="#18181b" className="dark:fill-zinc-300" />
          {/* Labels */}
          <text x={cx - r - 5} y={cy + 12} textAnchor="middle" fontSize="9" fill="#71717a">1x</text>
          <text x={cx} y={cy - r - 5} textAnchor="middle" fontSize="9" fill="#71717a">3x</text>
          <text x={cx + r + 5} y={cy + 12} textAnchor="middle" fontSize="9" fill="#71717a">5x</text>
        </svg>
      </div>
      <div className="mt-1 text-center">
        <p className="font-mono text-2xl font-semibold dark:text-white">{data.value.toFixed(1)}x</p>
        <p className="text-xs text-zinc-400">
          {data.leveraged_pct.toFixed(0)}% in leveraged products — {data.signal.replace(/_/g, " ")}
        </p>
      </div>
    </div>
  );
}
