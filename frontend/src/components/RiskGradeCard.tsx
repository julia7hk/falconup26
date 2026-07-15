"use client";

import { useState } from "react";
import type { RiskData } from "@/types";

const GRADE_COLORS: Record<string, string> = {
  A: "text-green-600 dark:text-green-400 border-green-300 bg-green-50 dark:border-green-700 dark:bg-green-950",
  B: "text-green-600 dark:text-green-400 border-green-200 bg-green-50/50 dark:border-green-800 dark:bg-green-950/50",
  C: "text-amber-600 dark:text-amber-400 border-amber-300 bg-amber-50 dark:border-amber-700 dark:bg-amber-950",
  D: "text-orange-600 dark:text-orange-400 border-orange-300 bg-orange-50 dark:border-orange-700 dark:bg-orange-950",
  F: "text-red-600 dark:text-red-400 border-red-300 bg-red-50 dark:border-red-700 dark:bg-red-950",
};

export function RiskGradeCard({ grade }: { grade: NonNullable<RiskData["risk_grade"]> }) {
  const [expanded, setExpanded] = useState(false);
  const colorClass = GRADE_COLORS[grade.grade] ?? GRADE_COLORS.C;
  return (
    <div className={`rounded-lg border ${colorClass}`}>
      <button onClick={() => setExpanded(!expanded)} className="w-full p-5 text-left">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-4">
            <span className="text-5xl font-bold">{grade.grade}</span>
            <div>
              <p className="text-sm font-medium dark:text-zinc-300">Portfolio Risk Grade</p>
              <p className="text-sm text-zinc-500 dark:text-zinc-400">{grade.interpretation}</p>
            </div>
          </div>
          <div className="flex items-center gap-2 sm:flex-col sm:items-end sm:gap-0">
            <p className="font-mono text-2xl font-semibold">{grade.score}</p>
            <p className="text-xs text-zinc-400">/ 100 {expanded ? "▲" : "▼"}</p>
          </div>
        </div>
      </button>
      {expanded && (
        <div className="border-t border-inherit px-5 pb-5 pt-3">
          <p className="mb-3 text-sm text-zinc-500 dark:text-zinc-400">
            Score = 100 minus penalties. Each component deducts points based on risk level.
          </p>
          <div className="flex flex-col gap-2">
            {Object.entries(grade.components).map(([key, comp]) => (
              <div key={key} className="flex items-center gap-3">
                <div className="w-24 text-sm font-medium capitalize text-zinc-600 dark:text-zinc-300">
                  {key}
                </div>
                <div className="flex-1">
                  <div className="h-2 rounded-full bg-zinc-200 dark:bg-zinc-700">
                    <div
                      className="h-2 rounded-full bg-red-500 dark:bg-red-400"
                      style={{ width: `${(comp.penalty / comp.max_penalty) * 100}%` }}
                    />
                  </div>
                </div>
                <span className="w-16 text-right font-mono text-sm text-zinc-500">
                  -{comp.penalty}/{comp.max_penalty}
                </span>
              </div>
            ))}
          </div>
          <div className="mt-3 flex flex-col gap-1">
            {Object.entries(grade.components).map(([key, comp]) => (
              <p key={key} className="text-xs text-zinc-400">
                <span className="font-medium capitalize">{key}:</span> {comp.reason}
              </p>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
