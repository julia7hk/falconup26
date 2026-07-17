"use client";

import { useRef, useEffect, useCallback, useMemo } from "react";
import type { PriceBar } from "@/types";

const TICK_INTERVALS = [
  0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000,
  2000, 5000,
];

function pickTickInterval(range: number, targetTicks: number): number {
  const rough = range / targetTicks;
  for (const t of TICK_INTERVALS) {
    if (t >= rough) return t;
  }
  return TICK_INTERVALS[TICK_INTERVALS.length - 1];
}

function formatPrice(v: number): string {
  if (v >= 1000) return v.toLocaleString(undefined, { maximumFractionDigits: 0 });
  if (v >= 100) return v.toFixed(1);
  if (v >= 1) return v.toFixed(2);
  return v.toFixed(4);
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

// Layout constants
const W = 700;
const H = 260;
const ML = 70;
const MR = 20;
const MT = 15;
const MB = 30;
const plotW = W - ML - MR;
const plotH = H - MT - MB;

function toX(i: number, count: number) {
  return ML + (i / (count - 1)) * plotW;
}

function toY(v: number, yMin: number, yRange: number) {
  return MT + plotH - ((v - yMin) / yRange) * plotH;
}

export function PriceChart({ data }: { data: PriceBar[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const vLineRef = useRef<SVGLineElement>(null);
  const hLineRef = useRef<SVGLineElement>(null);
  const dotRef = useRef<SVGCircleElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const crosshairGroupRef = useRef<SVGGElement>(null);

  // All derived data computed via useMemo — safe to use during render
  const chart = useMemo(() => {
    if (data.length < 2) return null;

    const closes = data.map((d) => d.close);
    const dataMin = Math.min(...closes);
    const dataMax = Math.max(...closes);
    const dataRange = dataMax - dataMin || 1;
    const yPad = dataRange * 0.05;
    const yMin = dataMin - yPad;
    const yMax = dataMax + yPad;
    const yRange = yMax - yMin;

    const xs = closes.map((_, i) => toX(i, closes.length));
    const ys = closes.map((c) => toY(c, yMin, yRange));

    // Y-axis ticks
    const tickInterval = pickTickInterval(dataRange, 5);
    const yTicks: number[] = [];
    const firstTick = Math.ceil(yMin / tickInterval) * tickInterval;
    for (let t = firstTick; t <= yMax; t += tickInterval) {
      yTicks.push(t);
    }

    // X-axis date labels
    const xLabelCount = Math.min(6, data.length);
    const xLabelStep = Math.max(1, Math.floor((data.length - 1) / (xLabelCount - 1)));
    const xLabels: { idx: number; label: string }[] = [];
    for (let i = 0; i < data.length; i += xLabelStep) {
      xLabels.push({ idx: i, label: formatDate(data[i].date, data.length) });
    }
    const lastLabel = xLabels[xLabels.length - 1];
    if (lastLabel.idx !== data.length - 1 && data.length - 1 - lastLabel.idx > xLabelStep * 0.5) {
      xLabels.push({
        idx: data.length - 1,
        label: formatDate(data[data.length - 1].date, data.length),
      });
    }

    // Paths
    const linePath = closes
      .map((c, i) => `${i === 0 ? "M" : "L"} ${toX(i, closes.length).toFixed(1)} ${toY(c, yMin, yRange).toFixed(1)}`)
      .join(" ");

    const areaPath =
      linePath +
      ` L ${toX(closes.length - 1, closes.length).toFixed(1)} ${toY(yMin, yMin, yRange).toFixed(1)}` +
      ` L ${toX(0, closes.length).toFixed(1)} ${toY(yMin, yMin, yRange).toFixed(1)} Z`;

    const trending = closes[closes.length - 1] >= closes[0];
    const lineColor = trending ? "#22c55e" : "#ef4444";

    return { closes, xs, ys, yMin, yRange, yTicks, xLabels, linePath, areaPath, lineColor };
  }, [data]);

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
      const bar = data[idx];

      if (crosshairGroupRef.current) crosshairGroupRef.current.style.display = "";
      if (vLineRef.current) {
        vLineRef.current.setAttribute("x1", String(cursorVBX));
        vLineRef.current.setAttribute("x2", String(cursorVBX));
      }
      if (hLineRef.current) {
        hLineRef.current.setAttribute("y1", String(dotY));
        hLineRef.current.setAttribute("y2", String(dotY));
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
        tooltip.innerHTML = `
          <p class="text-xs text-zinc-400">${formatTooltipDate(bar.date)}</p>
          <p class="font-mono font-semibold dark:text-white">$${bar.close.toFixed(2)}</p>
          <div class="mt-0.5 flex gap-3 text-xs text-zinc-400">
            <span>O ${bar.open.toFixed(2)}</span>
            <span>H ${bar.high.toFixed(2)}</span>
            <span>L ${bar.low.toFixed(2)}</span>
          </div>
        `;
      }
    },
    [data, chart],
  );

  const hideCrosshair = useCallback(() => {
    if (crosshairGroupRef.current) crosshairGroupRef.current.style.display = "none";
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

  if (!chart) return null;

  const { yTicks, xLabels, linePath, areaPath, lineColor } = chart;

  return (
    <div ref={containerRef} className="relative select-none touch-none">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        style={{ height: "clamp(200px, 30vw, 320px)" }}
      >
        {/* Grid lines */}
        {yTicks.map((t) => (
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
        {yTicks.map((t) => (
          <text
            key={`label-${t}`}
            x={ML - 8}
            y={toY(t, chart.yMin, chart.yRange) + 4}
            textAnchor="end"
            fontSize="11"
            fill="#a1a1aa"
            className="dark:fill-zinc-500"
          >
            ${formatPrice(t)}
          </text>
        ))}

        {/* X-axis labels */}
        {xLabels.map(({ idx, label }) => (
          <text
            key={`x-${idx}`}
            x={toX(idx, chart.closes.length)}
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
        <path d={areaPath} fill={lineColor} opacity={0.08} />

        {/* Line */}
        <path d={linePath} fill="none" stroke={lineColor} strokeWidth="1.5" />

        {/* Crosshair group — manipulated via refs, hidden by default */}
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
          <line
            ref={hLineRef}
            x1={ML}
            y1={MT}
            x2={W - MR}
            y2={MT}
            stroke="#71717a"
            strokeWidth="0.5"
            strokeDasharray="3,3"
          />
          <circle
            ref={dotRef}
            cx={ML}
            cy={MT}
            r="3.5"
            fill={lineColor}
            stroke="white"
            strokeWidth="1.5"
          />
        </g>
      </svg>

      {/* Tooltip — manipulated via ref, hidden by default */}
      <div
        ref={tooltipRef}
        className="pointer-events-none absolute top-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm shadow-md dark:border-zinc-700 dark:bg-zinc-900"
        style={{ display: "none" }}
      />
    </div>
  );
}
