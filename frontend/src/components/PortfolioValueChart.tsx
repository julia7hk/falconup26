"use client";

import { useRef, useEffect, useCallback, useMemo, useState } from "react";
import type { PortfolioValuePoint } from "@/types";

const TICK_INTERVALS = [
  0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000,
  2000, 5000, 10000, 20000, 50000, 100000,
];

function pickTickInterval(range: number, targetTicks: number): number {
  const rough = range / targetTicks;
  for (const t of TICK_INTERVALS) {
    if (t >= rough) return t;
  }
  return TICK_INTERVALS[TICK_INTERVALS.length - 1];
}

function formatDollars(v: number): string {
  if (v >= 1000)
    return v.toLocaleString(undefined, { maximumFractionDigits: 0 });
  return v.toFixed(0);
}

function formatDate(dateStr: string, totalDays: number): string {
  const d = new Date(dateStr + "T00:00:00");
  if (totalDays <= 180) {
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  }
  return d.toLocaleDateString(undefined, { month: "short", year: "2-digit" });
}

function formatTooltipDate(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

const money = (n: number) =>
  n.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

// Layout constants (match PriceChart, wider left margin for $ labels)
const W = 700;
const H = 260;
const ML = 78;
const MR = 20;
const MT = 15;
const MB = 30;
const plotW = W - ML - MR;
const plotH = H - MT - MB;

function toX(i: number, count: number) {
  return count <= 1 ? ML : ML + (i / (count - 1)) * plotW;
}

function toY(v: number, yMin: number, yRange: number) {
  return MT + plotH - ((v - yMin) / yRange) * plotH;
}

const RANGES = [
  { key: "1M", label: "1M", days: 30 },
  { key: "3M", label: "3M", days: 90 },
  { key: "6M", label: "6M", days: 180 },
  { key: "1Y", label: "1Y", days: 365 },
  { key: "ALL", label: "All", days: Infinity },
] as const;

type RangeKey = (typeof RANGES)[number]["key"];

export function PortfolioValueChart({
  series,
  totalCost,
  complete,
}: {
  series: PortfolioValuePoint[];
  totalCost: number;
  complete: boolean;
}) {
  const [range, setRange] = useState<RangeKey>("1Y");

  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const vLineRef = useRef<SVGLineElement>(null);
  const dotRef = useRef<SVGCircleElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const crosshairGroupRef = useRef<SVGGElement>(null);

  // Slice the full series to the selected range (client-side; no refetch).
  const data = useMemo(() => {
    const days = RANGES.find((r) => r.key === range)!.days;
    if (days === Infinity || series.length === 0) return series;
    const last = new Date(series[series.length - 1].date + "T00:00:00");
    const cutoff = new Date(last);
    cutoff.setDate(cutoff.getDate() - days);
    const cutoffStr = cutoff.toISOString().slice(0, 10);
    return series.filter((p) => p.date >= cutoffStr);
  }, [series, range]);

  const chart = useMemo(() => {
    if (data.length < 2) return null;

    const values = data.map((d) => d.value);
    // Include the cost basis in the y-domain so the break-even line is on-chart.
    const dataMin = Math.min(...values, totalCost);
    const dataMax = Math.max(...values, totalCost);
    const dataRange = dataMax - dataMin || 1;
    const yPad = dataRange * 0.08;
    const yMin = dataMin - yPad;
    const yMax = dataMax + yPad;
    const yRange = yMax - yMin;

    const xs = values.map((_, i) => toX(i, values.length));
    const ys = values.map((v) => toY(v, yMin, yRange));

    const tickInterval = pickTickInterval(dataRange, 5);
    const yTicks: number[] = [];
    const firstTick = Math.ceil(yMin / tickInterval) * tickInterval;
    for (let t = firstTick; t <= yMax; t += tickInterval) {
      yTicks.push(t);
    }

    const xLabelCount = Math.min(6, data.length);
    const xLabelStep = Math.max(
      1,
      Math.floor((data.length - 1) / (xLabelCount - 1)),
    );
    const xLabels: { idx: number; label: string }[] = [];
    for (let i = 0; i < data.length; i += xLabelStep) {
      xLabels.push({ idx: i, label: formatDate(data[i].date, data.length) });
    }
    const lastLabel = xLabels[xLabels.length - 1];
    if (
      lastLabel.idx !== data.length - 1 &&
      data.length - 1 - lastLabel.idx > xLabelStep * 0.5
    ) {
      xLabels.push({
        idx: data.length - 1,
        label: formatDate(data[data.length - 1].date, data.length),
      });
    }

    const linePath = values
      .map(
        (v, i) =>
          `${i === 0 ? "M" : "L"} ${toX(i, values.length).toFixed(1)} ${toY(v, yMin, yRange).toFixed(1)}`,
      )
      .join(" ");

    const baseY = toY(yMin, yMin, yRange);
    const areaPath =
      linePath +
      ` L ${toX(values.length - 1, values.length).toFixed(1)} ${baseY.toFixed(1)}` +
      ` L ${toX(0, values.length).toFixed(1)} ${baseY.toFixed(1)} Z`;

    // In profit (above cost) → green, else red.
    const inProfit = values[values.length - 1] >= totalCost;
    const lineColor = inProfit ? "#22c55e" : "#ef4444";
    const costY = toY(totalCost, yMin, yRange);

    return {
      values,
      xs,
      ys,
      yMin,
      yRange,
      yTicks,
      xLabels,
      linePath,
      areaPath,
      lineColor,
      costY,
    };
  }, [data, totalCost]);

  const updateCrosshair = useCallback(
    (clientX: number) => {
      const svg = svgRef.current;
      if (!svg || !chart) return;

      const rect = svg.getBoundingClientRect();
      const pxFraction = (clientX - rect.left) / rect.width;
      const cursorVBX = Math.max(ML, Math.min(W - MR, pxFraction * W));
      const plotFraction = (cursorVBX - ML) / plotW;
      const idx = Math.max(
        0,
        Math.min(data.length - 1, Math.round(plotFraction * (data.length - 1))),
      );

      const dotX = chart.xs[idx];
      const dotY = chart.ys[idx];
      const point = data[idx];
      const pnl = point.value - totalCost;
      const pnlPct = totalCost > 0 ? (pnl / totalCost) * 100 : 0;

      if (crosshairGroupRef.current)
        crosshairGroupRef.current.style.display = "";
      if (vLineRef.current) {
        vLineRef.current.setAttribute("x1", String(cursorVBX));
        vLineRef.current.setAttribute("x2", String(cursorVBX));
      }
      if (dotRef.current) {
        dotRef.current.setAttribute("cx", String(dotX));
        dotRef.current.setAttribute("cy", String(dotY));
      }

      const tooltip = tooltipRef.current;
      if (tooltip) {
        tooltip.style.display = "block";
        const pct = (cursorVBX / W) * 100;
        tooltip.style.left = `${pct}%`;
        tooltip.style.transform =
          pct > 70
            ? "translateX(-100%)"
            : pct < 30
              ? "translateX(0)"
              : "translateX(-50%)";
        const pnlColor = pnl >= 0 ? "#16a34a" : "#dc2626";
        const sign = pnl >= 0 ? "+" : "";
        tooltip.innerHTML = `
          <p class="text-xs text-zinc-400">${formatTooltipDate(point.date)}</p>
          <p class="font-mono font-semibold dark:text-white">$${money(point.value)}</p>
          <p class="font-mono text-xs" style="color:${pnlColor}">
            ${sign}$${money(pnl)} (${sign}${pnlPct.toFixed(2)}%)
          </p>
        `;
      }
    },
    [data, chart, totalCost],
  );

  const hideCrosshair = useCallback(() => {
    if (crosshairGroupRef.current)
      crosshairGroupRef.current.style.display = "none";
    if (tooltipRef.current) tooltipRef.current.style.display = "none";
  }, []);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    function onPointerMove(e: PointerEvent) {
      e.preventDefault();
      updateCrosshair(e.clientX);
    }
    function onPointerLeave() {
      hideCrosshair();
    }

    el.addEventListener("pointermove", onPointerMove, { passive: false });
    el.addEventListener("pointerleave", onPointerLeave);
    el.addEventListener("pointercancel", onPointerLeave);
    return () => {
      el.removeEventListener("pointermove", onPointerMove);
      el.removeEventListener("pointerleave", onPointerLeave);
      el.removeEventListener("pointercancel", onPointerLeave);
    };
  }, [updateCrosshair, hideCrosshair]);

  return (
    <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-700">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-zinc-500 dark:text-zinc-400">
            Portfolio Value Over Time
          </p>
          <p className="text-xs text-zinc-400">
            Value of your current holdings on each past trading day, vs. your
            cost basis.
          </p>
        </div>
        <div className="flex gap-1">
          {RANGES.map((r) => (
            <button
              key={r.key}
              onClick={() => setRange(r.key)}
              className={`rounded px-2 py-1 text-xs font-medium ${
                range === r.key
                  ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                  : "text-zinc-500 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800"
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {!complete && (
        <p className="mb-2 text-xs text-amber-600 dark:text-amber-400">
          A holding is missing price history and was left out of this chart.
        </p>
      )}

      {!chart ? (
        <p className="py-12 text-center text-sm text-zinc-400">
          Not enough price history to chart this range.
        </p>
      ) : (
        <div
          ref={containerRef}
          className="relative select-none touch-none"
        >
          <svg
            ref={svgRef}
            viewBox={`0 0 ${W} ${H}`}
            className="w-full"
            style={{ height: "clamp(200px, 30vw, 320px)" }}
          >
            {/* Grid lines */}
            {chart.yTicks.map((t) => (
              <line
                key={t}
                x1={ML}
                y1={toY(t, chart.yMin, chart.yRange)}
                x2={W - MR}
                y2={toY(t, chart.yMin, chart.yRange)}
                stroke="#e4e4e7"
                strokeWidth="0.5"
                className="dark:stroke-zinc-800"
              />
            ))}

            {/* Y-axis labels */}
            {chart.yTicks.map((t) => (
              <text
                key={`label-${t}`}
                x={ML - 8}
                y={toY(t, chart.yMin, chart.yRange) + 4}
                textAnchor="end"
                fontSize="11"
                fill="#a1a1aa"
                className="dark:fill-zinc-500"
              >
                ${formatDollars(t)}
              </text>
            ))}

            {/* X-axis labels */}
            {chart.xLabels.map(({ idx, label }) => (
              <text
                key={`x-${idx}`}
                x={toX(idx, chart.values.length)}
                y={H - 6}
                textAnchor="middle"
                fontSize="10"
                fill="#a1a1aa"
                className="dark:fill-zinc-500"
              >
                {label}
              </text>
            ))}

            {/* Area fill */}
            <path d={chart.areaPath} fill={chart.lineColor} opacity={0.08} />

            {/* Cost-basis (break-even) line */}
            <line
              x1={ML}
              y1={chart.costY}
              x2={W - MR}
              y2={chart.costY}
              stroke="#a1a1aa"
              strokeWidth="1"
              strokeDasharray="4,3"
            />
            <text
              x={W - MR}
              y={chart.costY - 4}
              textAnchor="end"
              fontSize="10"
              fill="#a1a1aa"
            >
              Cost ${formatDollars(totalCost)}
            </text>

            {/* Value line */}
            <path
              d={chart.linePath}
              fill="none"
              stroke={chart.lineColor}
              strokeWidth="1.5"
            />

            {/* Crosshair group */}
            <g ref={crosshairGroupRef} style={{ display: "none" }}>
              <line
                ref={vLineRef}
                x1={ML}
                y1={MT}
                x2={ML}
                y2={MT + plotH}
                stroke="#71717a"
                strokeWidth="0.5"
                strokeDasharray="3,3"
              />
              <circle
                ref={dotRef}
                cx={ML}
                cy={MT}
                r="3.5"
                fill={chart.lineColor}
                stroke="white"
                strokeWidth="1.5"
              />
            </g>
          </svg>

          {/* Tooltip */}
          <div
            ref={tooltipRef}
            className="pointer-events-none absolute top-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm shadow-md dark:border-zinc-700 dark:bg-zinc-900"
            style={{ display: "none" }}
          />
        </div>
      )}
    </div>
  );
}
