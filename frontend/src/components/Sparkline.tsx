import type { PriceBar } from "@/types";

export function Sparkline({ data }: { data: PriceBar[] }) {
  if (data.length < 2) return null;
  const closes = data.map((d) => d.close);
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const range = max - min || 1;
  const w = 600;
  const h = 120;
  const points = closes
    .map((c, i) => {
      const x = (i / (closes.length - 1)) * w;
      const y = h - ((c - min) / range) * (h - 10) - 5;
      return `${x},${y}`;
    })
    .join(" ");
  const trending = closes[closes.length - 1] >= closes[0];
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-48">
      <polyline
        fill="none"
        stroke={trending ? "#22c55e" : "#ef4444"}
        strokeWidth="2"
        points={points}
      />
    </svg>
  );
}
