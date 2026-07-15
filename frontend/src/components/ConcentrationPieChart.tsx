import type { RiskData } from "@/types";

const SECTOR_COLORS = [
  "#3b82f6", "#ef4444", "#22c55e", "#f59e0b", "#8b5cf6",
  "#ec4899", "#14b8a6", "#f97316", "#6366f1", "#84cc16",
];

export function ConcentrationPieChart({ data }: { data: NonNullable<RiskData["concentration"]> }) {
  const entries = Object.entries(data.sector_breakdown).sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((s, [, v]) => s + v, 0);

  // Build SVG arc paths
  const cx = 80, cy = 80, r = 70;
  // Pre-compute cumulative start angles to avoid mutation during render
  const angles = entries.map(([, pct]) => (pct / total) * 2 * Math.PI);
  const cumAngles = angles.reduce<number[]>((acc, a) => {
    acc.push((acc.length > 0 ? acc[acc.length - 1] : 0) + a);
    return acc;
  }, []);
  const arcs = entries.map(([sector, pct], i) => {
    const startAngle = -Math.PI / 2 + (i > 0 ? cumAngles[i - 1] : 0);
    const endAngle = -Math.PI / 2 + cumAngles[i];
    const startX = cx + r * Math.cos(startAngle);
    const startY = cy + r * Math.sin(startAngle);
    const endX = cx + r * Math.cos(endAngle);
    const endY = cy + r * Math.sin(endAngle);
    const largeArc = angles[i] > Math.PI ? 1 : 0;
    const path = entries.length === 1
      ? `M ${cx} ${cy - r} A ${r} ${r} 0 1 1 ${cx - 0.01} ${cy - r} Z`
      : `M ${cx} ${cy} L ${startX} ${startY} A ${r} ${r} 0 ${largeArc} 1 ${endX} ${endY} Z`;
    return { sector, pct, path, color: SECTOR_COLORS[i % SECTOR_COLORS.length] };
  });

  return (
    <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-700">
      <p className="text-sm font-medium text-zinc-500 dark:text-zinc-400">Concentration</p>
      <div className="mt-2 flex items-center gap-4">
        <svg viewBox="0 0 160 160" className="h-28 w-28 shrink-0">
          {arcs.map((a) => (
            <path key={a.sector} d={a.path} fill={a.color} stroke="white" strokeWidth="1" />
          ))}
        </svg>
        <div className="flex flex-col gap-1">
          {arcs.map((a) => (
            <div key={a.sector} className="flex items-center gap-2 text-xs">
              <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: a.color }} />
              <span className="text-zinc-600 dark:text-zinc-300">{a.sector}</span>
              <span className="font-mono text-zinc-400">{a.pct.toFixed(1)}%</span>
            </div>
          ))}
        </div>
      </div>
      <p className="mt-2 text-xs text-zinc-400">
        HHI: {data.herfindahl_index.toFixed(2)} — {data.signal.replace(/_/g, " ")}
      </p>
    </div>
  );
}
