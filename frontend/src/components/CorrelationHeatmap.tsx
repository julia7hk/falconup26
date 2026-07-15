import type { CorrelationData } from "@/types";

export function CorrelationHeatmap({ data }: { data: CorrelationData }) {
  if (!data.tickers.length || !data.avg_pairwise) return null;
  const tickers = data.tickers;
  const n = tickers.length;
  const cellSize = 50;
  const labelW = 50;
  const svgW = labelW + n * cellSize;
  const svgH = labelW + n * cellSize;

  function corrColor(v: number): string {
    if (v >= 0) {
      const t = Math.min(v, 1);
      return `rgb(255,${Math.round(255 * (1 - t * 0.7))},${Math.round(255 * (1 - t * 0.7))})`;
    } else {
      const t = Math.min(-v, 1);
      return `rgb(${Math.round(255 * (1 - t * 0.7))},${Math.round(255 * (1 - t * 0.7))},255)`;
    }
  }

  // Cap rendered width so it doesn't stretch full-width for 2-3 tickers
  const maxPx = Math.min(400, (n + 1) * 70);

  return (
    <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-700">
      <p className="text-sm font-medium text-zinc-500 dark:text-zinc-400">Correlation Matrix</p>
      <div className="mt-2 flex justify-center overflow-x-auto">
        <svg viewBox={`0 0 ${svgW} ${svgH}`} className="max-w-full" style={{ width: maxPx, height: maxPx * (svgH / svgW) }}>
          {/* Column labels */}
          {tickers.map((t, j) => (
            <text
              key={`col-${t}`}
              x={labelW + j * cellSize + cellSize / 2}
              y={labelW - 6}
              textAnchor="middle"
              fontSize="11"
              fill="#71717a"
            >
              {t}
            </text>
          ))}
          {/* Row labels + cells */}
          {tickers.map((t1, i) => (
            <g key={t1}>
              <text
                x={labelW - 6}
                y={labelW + i * cellSize + cellSize / 2 + 4}
                textAnchor="end"
                fontSize="11"
                fill="#71717a"
              >
                {t1}
              </text>
              {tickers.map((t2, j) => {
                const v = data.matrix[t1]?.[t2] ?? 0;
                return (
                  <g key={`${t1}-${t2}`}>
                    <rect
                      x={labelW + j * cellSize + 1}
                      y={labelW + i * cellSize + 1}
                      width={cellSize - 2}
                      height={cellSize - 2}
                      fill={corrColor(v)}
                      rx={3}
                    />
                    <text
                      x={labelW + j * cellSize + cellSize / 2}
                      y={labelW + i * cellSize + cellSize / 2 + 4}
                      textAnchor="middle"
                      fontSize="11"
                      fontWeight="500"
                      fill={Math.abs(v) > 0.5 ? "white" : "#333"}
                    >
                      {v.toFixed(2)}
                    </text>
                  </g>
                );
              })}
            </g>
          ))}
        </svg>
      </div>
      <p className="mt-2 text-xs text-zinc-400">
        Avg pairwise: {data.avg_pairwise.toFixed(2)}
        {data.max_pair && ` — most correlated: ${data.max_pair[0]}/${data.max_pair[1]} (${data.max_pair[2].toFixed(2)})`}
        {data.signal && ` — ${data.signal.replace(/_/g, " ")}`}
      </p>
    </div>
  );
}
