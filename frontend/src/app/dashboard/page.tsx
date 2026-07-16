"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { authClient } from "@/lib/auth-client";
import type {
  IndicatorData,
  Portfolio,
  RiskData,
  CorrelationData,
  StressData,
} from "@/types";
import { RiskGradeCard } from "@/components/RiskGradeCard";
import { ConcentrationPieChart } from "@/components/ConcentrationPieChart";
import { CorrelationHeatmap } from "@/components/CorrelationHeatmap";
import { LeverageGauge } from "@/components/LeverageGauge";
import { StressScenarioCard } from "@/components/StressScenarioCard";

type Status =
  | { kind: "idle" }
  | { kind: "saving" }
  | { kind: "ok"; msg: string }
  | { kind: "err"; msg: string };

function StatusLine({ status }: { status: Status }) {
  if (status.kind === "idle" || status.kind === "saving") return null;
  return (
    <p
      className={`text-xs ${
        status.kind === "ok"
          ? "text-green-600 dark:text-green-400"
          : "text-red-600 dark:text-red-400"
      }`}
    >
      {status.msg}
    </p>
  );
}

const sectionCls =
  "space-y-3 rounded-lg border border-zinc-200 p-5 dark:border-zinc-700";
const labelCls = "block text-sm text-zinc-500 dark:text-zinc-400";
const inputCls =
  "w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-white";
const btnCls =
  "rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300";

export default function DashboardPage() {
  const router = useRouter();
  const { data: session, isPending } = authClient.useSession();

  const [name, setName] = useState(session?.user.name || "");
  const [profileStatus, setProfileStatus] = useState<Status>({ kind: "idle" });

  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [pwStatus, setPwStatus] = useState<Status>({ kind: "idle" });

  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [addTicker, setAddTicker] = useState("");
  const [addShares, setAddShares] = useState("");
  const [addAvgCost, setAddAvgCost] = useState("");
  const [addError, setAddError] = useState("");
  const [addLoading, setAddLoading] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editShares, setEditShares] = useState("");
  const [editAvgCost, setEditAvgCost] = useState("");
  const [portfolioError, setPortfolioError] = useState("");
  const [holdingSignals, setHoldingSignals] = useState<
    Record<string, { signal: string; confidence: number }>
  >({});
  const [riskData, setRiskData] = useState<RiskData | null>(null);
  const [correlationData, setCorrelationData] = useState<CorrelationData | null>(null);
  const [stressData, setStressData] = useState<StressData | null>(null);
  const [riskLoading, setRiskLoading] = useState(false);

  useEffect(() => {
    if (!isPending && !session) {
      router.push("/sign-in?redirect=/dashboard");
    }
  }, [isPending, session, router]);

  useEffect(() => {
    if (session) fetchPortfolio();
  }, [session]);

  async function fetchPortfolio() {
    try {
      const res = await fetch("/api/portfolio", { credentials: "include" });
      if (!res.ok) return;
      const data: Portfolio = await res.json();
      setPortfolio(data);

      const tickers = data.holdings.map((h) => h.ticker);
      const signals: Record<string, { signal: string; confidence: number }> = {};
      await Promise.all(
        tickers.map(async (ticker) => {
          try {
            const r = await fetch(`/api/symbols/${ticker}/indicators`);
            if (r.ok) {
              const ind: IndicatorData = await r.json();
              signals[ticker] = {
                signal: ind.composite.signal,
                confidence: ind.composite.confidence,
              };
            }
          } catch {}
        }),
      );
      setHoldingSignals(signals);
      if (data.holdings.length > 0) fetchRiskData();
    } catch {}
  }

  async function fetchRiskData() {
    setRiskLoading(true);
    try {
      const [riskRes, corrRes, stressRes] = await Promise.all([
        fetch("/api/portfolio/risk", { credentials: "include" }),
        fetch("/api/portfolio/correlation", { credentials: "include" }),
        fetch("/api/portfolio/stress?scenario=all", { credentials: "include" }),
      ]);
      if (riskRes.ok) setRiskData(await riskRes.json());
      if (corrRes.ok) setCorrelationData(await corrRes.json());
      if (stressRes.ok) setStressData(await stressRes.json());
    } catch {}
    setRiskLoading(false);
  }

  async function addHolding() {
    if (!addTicker.trim() || !addShares || !addAvgCost) return;
    const shares = parseFloat(addShares);
    const avgCost = parseFloat(addAvgCost);
    if (isNaN(shares) || shares <= 0 || isNaN(avgCost) || avgCost <= 0) {
      setAddError("Shares and avg cost must be positive numbers");
      return;
    }
    setAddError("");
    setAddLoading(true);
    try {
      const res = await fetch("/api/portfolio/holdings", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticker: addTicker.toUpperCase(),
          shares: parseFloat(addShares),
          avg_cost: parseFloat(addAvgCost),
        }),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || `Failed (${res.status})`);
      }
      setAddTicker("");
      setAddShares("");
      setAddAvgCost("");
      setShowAddForm(false);
      await fetchPortfolio();
    } catch (e) {
      setAddError(e instanceof Error ? e.message : "Failed to add holding");
    } finally {
      setAddLoading(false);
    }
  }

  async function updateHolding(id: number) {
    setPortfolioError("");
    try {
      const shares = editShares ? parseFloat(editShares) : undefined;
      const avgCost = editAvgCost ? parseFloat(editAvgCost) : undefined;
      if (
        (shares !== undefined && (isNaN(shares) || shares <= 0)) ||
        (avgCost !== undefined && (isNaN(avgCost) || avgCost <= 0))
      ) {
        setPortfolioError("Shares and avg cost must be positive numbers");
        return;
      }
      const body: Record<string, number> = {};
      if (shares !== undefined) body.shares = shares;
      if (avgCost !== undefined) body.avg_cost = avgCost;
      const res = await fetch(`/api/portfolio/holdings/${id}`, {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || `Update failed (${res.status})`);
      }
      setEditingId(null);
      await fetchPortfolio();
    } catch (e) {
      setPortfolioError(e instanceof Error ? e.message : "Failed to update holding");
    }
  }

  async function deleteHolding(id: number) {
    setPortfolioError("");
    try {
      const res = await fetch(`/api/portfolio/holdings/${id}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || `Delete failed (${res.status})`);
      }
      await fetchPortfolio();
    } catch (e) {
      setPortfolioError(e instanceof Error ? e.message : "Failed to delete holding");
    }
  }

  async function saveName(e: React.FormEvent) {
    e.preventDefault();
    setProfileStatus({ kind: "saving" });
    try {
      const { error } = await authClient.updateUser({ name });
      if (error) throw new Error(error.message ?? "Update failed");
      setProfileStatus({ kind: "ok", msg: "Name updated." });
      router.refresh();
    } catch (err) {
      setProfileStatus({
        kind: "err",
        msg: err instanceof Error ? err.message : "Update failed",
      });
    }
  }

  async function savePassword(e: React.FormEvent) {
    e.preventDefault();
    if (newPw.length < 8) {
      setPwStatus({ kind: "err", msg: "Password must be at least 8 characters." });
      return;
    }
    setPwStatus({ kind: "saving" });
    try {
      const { error } = await authClient.changePassword({
        currentPassword: currentPw,
        newPassword: newPw,
      });
      if (error) throw new Error(error.message ?? "Change failed");
      setPwStatus({ kind: "ok", msg: "Password changed." });
      setCurrentPw("");
      setNewPw("");
    } catch (err) {
      setPwStatus({
        kind: "err",
        msg: err instanceof Error ? err.message : "Change failed",
      });
    }
  }

  if (isPending || !session) return null;

  const fmt = (n: number) =>
    n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  return (
    <div className="flex flex-col flex-1 items-center bg-zinc-50 font-sans dark:bg-zinc-950">
      <main className="flex flex-1 w-full max-w-6xl flex-col gap-6 py-8 px-4 sm:py-12 sm:px-8">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold tracking-tight dark:text-white">
            Dashboard
          </h1>
          <Link
            href="/"
            className="text-sm text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200"
          >
            ← Back to Market
          </Link>
        </div>

        {/* Portfolio Section */}
        <section className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold dark:text-zinc-200">
              My Portfolio
              {portfolio && portfolio.holdings.length > 0 && (
                <span className="ml-2 text-base font-normal text-zinc-400">
                  {portfolio.holdings.length} holding{portfolio.holdings.length !== 1 ? "s" : ""}
                </span>
              )}
            </h2>
            <button
              onClick={() => setShowAddForm(!showAddForm)}
              className={btnCls}
            >
              {showAddForm ? "Cancel" : "+ Add Holding"}
            </button>
          </div>

          {/* Add Holding Form */}
          {showAddForm && (
            <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-700">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                <div className="flex-1">
                  <label className={labelCls}>Symbol</label>
                  <input
                    type="text"
                    value={addTicker}
                    onChange={(e) => setAddTicker(e.target.value.toUpperCase())}
                    placeholder="e.g. QQQ"
                    className={inputCls}
                  />
                </div>
                <div className="flex-1">
                  <label className={labelCls}>Shares</label>
                  <input
                    type="number"
                    value={addShares}
                    onChange={(e) => setAddShares(e.target.value)}
                    placeholder="10"
                    min="0"
                    step="any"
                    className={inputCls}
                  />
                </div>
                <div className="flex-1">
                  <label className={labelCls}>Avg Cost ($)</label>
                  <input
                    type="number"
                    value={addAvgCost}
                    onChange={(e) => setAddAvgCost(e.target.value)}
                    placeholder="480.00"
                    min="0"
                    step="any"
                    className={inputCls}
                  />
                </div>
                <button onClick={addHolding} disabled={addLoading} className={btnCls}>
                  {addLoading ? "Adding..." : "Add"}
                </button>
              </div>
              {addError && (
                <p className="mt-2 text-sm text-red-600 dark:text-red-400">{addError}</p>
              )}
              <p className="mt-2 text-xs text-zinc-400">
                Symbol must be in the database. Try: QQQ, TQQQ, SOXL, SPY, AAPL, MSFT, NVDA, GOOGL, AMZN, META, TSLA
              </p>
            </div>
          )}

          {/* Portfolio Error */}
          {portfolioError && (
            <p className="text-sm text-red-600 dark:text-red-400">{portfolioError}</p>
          )}

          {/* Portfolio Summary */}
          {portfolio && portfolio.holdings.length > 0 && (
            <>
              {!portfolio.prices_complete && (
                <p className="text-sm text-amber-600 dark:text-amber-400">
                  Some prices are unavailable — totals may be incomplete.
                </p>
              )}
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
                  <p className="text-sm text-zinc-500 dark:text-zinc-400">Total Value</p>
                  <p className="font-mono text-xl font-semibold dark:text-white">
                    ${fmt(portfolio.total_value)}
                  </p>
                </div>
                <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
                  <p className="text-sm text-zinc-500 dark:text-zinc-400">Total Cost</p>
                  <p className="font-mono text-xl font-semibold dark:text-white">
                    ${fmt(portfolio.total_cost)}
                  </p>
                </div>
                <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
                  <p className="text-sm text-zinc-500 dark:text-zinc-400">Total P&L</p>
                  <p
                    className={`font-mono text-xl font-semibold ${
                      portfolio.total_pnl >= 0
                        ? "text-green-600 dark:text-green-400"
                        : "text-red-600 dark:text-red-400"
                    }`}
                  >
                    {portfolio.total_pnl >= 0 ? "+" : ""}${fmt(portfolio.total_pnl)}
                  </p>
                </div>
              </div>
            </>
          )}

          {/* Holdings List */}
          {portfolio && portfolio.holdings.length > 0 ? (
            <div className="flex flex-col gap-3">
              {portfolio.holdings.map((h) => (
                <div
                  key={h.id}
                  className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-700"
                >
                  {editingId === h.id ? (
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                      <div>
                        <p className="font-mono text-lg font-bold dark:text-white">{h.ticker}</p>
                        <p className="text-sm text-zinc-400">{h.name}</p>
                      </div>
                      <div className="flex-1">
                        <label className="mb-1 block text-xs text-zinc-400">Shares</label>
                        <input
                          type="number"
                          value={editShares}
                          onChange={(e) => setEditShares(e.target.value)}
                          min="0"
                          step="any"
                          className="w-full rounded border border-zinc-300 px-2 py-1 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-white"
                        />
                      </div>
                      <div className="flex-1">
                        <label className="mb-1 block text-xs text-zinc-400">Avg Cost ($)</label>
                        <input
                          type="number"
                          value={editAvgCost}
                          onChange={(e) => setEditAvgCost(e.target.value)}
                          min="0"
                          step="any"
                          className="w-full rounded border border-zinc-300 px-2 py-1 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-white"
                        />
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={() => updateHolding(h.id)}
                          className="rounded bg-zinc-900 px-3 py-1 text-sm text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900"
                        >
                          Save
                        </button>
                        <button
                          onClick={() => setEditingId(null)}
                          className="rounded border border-zinc-300 px-3 py-1 text-sm hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                      <div>
                        <div className="flex items-baseline gap-2">
                          <Link
                            href={`/?symbol=${h.ticker}`}
                            className="font-mono text-lg font-bold hover:text-blue-600 dark:text-white dark:hover:text-blue-400"
                          >
                            {h.ticker}
                          </Link>
                          {h.leverage_factor !== 1 && (
                            <span className="rounded bg-amber-100 px-1 text-xs font-medium text-amber-700 dark:bg-amber-900 dark:text-amber-300">
                              {h.leverage_factor}x
                            </span>
                          )}
                          {holdingSignals[h.ticker] && (
                            <span
                              className={`rounded px-1.5 py-0.5 text-xs font-semibold uppercase ${
                                holdingSignals[h.ticker].signal === "buy"
                                  ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
                                  : holdingSignals[h.ticker].signal === "sell"
                                    ? "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300"
                                    : "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400"
                              }`}
                            >
                              {holdingSignals[h.ticker].signal}
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-zinc-400">{h.name}</p>
                      </div>
                      <div className="flex flex-wrap items-center gap-4 sm:gap-6">
                        <div className="sm:text-right">
                          <p className="text-sm text-zinc-500 dark:text-zinc-400">
                            {h.shares} shares @ ${h.avg_cost.toFixed(2)}
                          </p>
                          {h.price !== null && (
                            <p className="font-mono text-base font-semibold dark:text-zinc-200">
                              ${h.market_value!.toLocaleString(undefined, {
                                minimumFractionDigits: 2,
                                maximumFractionDigits: 2,
                              })}
                            </p>
                          )}
                        </div>
                        <div className="sm:text-right">
                          {h.pnl !== null && (
                            <>
                              <p
                                className={`font-mono text-base font-semibold ${
                                  h.pnl >= 0
                                    ? "text-green-600 dark:text-green-400"
                                    : "text-red-600 dark:text-red-400"
                                }`}
                              >
                                {h.pnl >= 0 ? "+" : ""}${h.pnl.toFixed(2)}
                              </p>
                              <p
                                className={`text-sm ${
                                  h.pnl_percent! >= 0
                                    ? "text-green-600 dark:text-green-400"
                                    : "text-red-600 dark:text-red-400"
                                }`}
                              >
                                {h.pnl_percent! >= 0 ? "+" : ""}
                                {h.pnl_percent!.toFixed(2)}%
                              </p>
                            </>
                          )}
                          {h.price === null && (
                            <p className="text-sm text-zinc-400">Price unavailable</p>
                          )}
                        </div>
                        <div className="flex gap-1">
                          <button
                            onClick={() => {
                              setEditingId(h.id);
                              setEditShares(String(h.shares));
                              setEditAvgCost(String(h.avg_cost));
                            }}
                            className="rounded border border-zinc-300 px-2 py-1 text-xs hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-800"
                          >
                            Edit
                          </button>
                          <button
                            onClick={() => deleteHolding(h.id)}
                            className="rounded border border-red-200 px-2 py-1 text-xs text-red-600 hover:bg-red-50 dark:border-red-900 dark:text-red-400 dark:hover:bg-red-950"
                          >
                            Delete
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : portfolio && portfolio.holdings.length === 0 ? (
            <div className="rounded-lg border border-dashed border-zinc-300 p-8 text-center dark:border-zinc-700">
              <p className="text-lg font-medium text-zinc-500 dark:text-zinc-400">
                No holdings yet
              </p>
              <p className="mt-1 text-sm text-zinc-400">
                Add your first holding to start tracking your portfolio.
              </p>
              <button
                onClick={() => setShowAddForm(true)}
                className="mt-4 rounded-lg bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
              >
                + Add Your First Holding
              </button>
            </div>
          ) : null}
        </section>

        {/* Portfolio Risk Analysis */}
        {portfolio && portfolio.holdings.length > 0 && riskData && (
          <section className="flex flex-col gap-4 border-t border-zinc-300 pt-6 dark:border-zinc-600">
            <div>
              <h2 className="text-xl font-bold dark:text-zinc-200">Risk Analysis</h2>
              <p className="mt-1 text-xs text-zinc-400">
                Based on historical data and portfolio composition. These are analytical measurements, not predictions or financial advice.
              </p>
            </div>

            {riskData.risk_grade && <RiskGradeCard grade={riskData.risk_grade} />}

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {riskData.concentration && <ConcentrationPieChart data={riskData.concentration} />}
              {riskData.effective_leverage && <LeverageGauge data={riskData.effective_leverage} />}
              {riskData.portfolio_beta && (
                <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-700">
                  <p className="text-sm font-medium text-zinc-500 dark:text-zinc-400">Portfolio Beta</p>
                  <p className="mt-2 font-mono text-3xl font-semibold dark:text-white">
                    {riskData.portfolio_beta.value.toFixed(2)}
                  </p>
                  <p className="mt-1 text-xs text-zinc-400">{riskData.portfolio_beta.interpretation}</p>
                  <p className="mt-1 text-xs text-zinc-400">
                    A 10% market drop ≈ {(riskData.portfolio_beta.value * 10).toFixed(0)}% portfolio drop
                  </p>
                </div>
              )}
            </div>

            {correlationData && correlationData.tickers.length >= 2 && (
              <CorrelationHeatmap data={correlationData} />
            )}

            {riskData.max_drawdown && (
              <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-700">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="text-sm font-medium text-zinc-500 dark:text-zinc-400">
                      Historical Max Drawdown
                    </p>
                    <p className="font-mono text-2xl font-semibold text-red-600 dark:text-red-400">
                      -{riskData.max_drawdown.value.toFixed(1)}%
                    </p>
                  </div>
                  <div className="sm:text-right">
                    <p className="text-xs text-zinc-400">Worst period</p>
                    <p className="text-sm text-zinc-500 dark:text-zinc-400">
                      {riskData.max_drawdown.worst_start} to {riskData.max_drawdown.worst_end}
                    </p>
                    <p className="text-xs text-zinc-400">
                      Annualized volatility: {riskData.max_drawdown.annualized_vol.toFixed(1)}%
                    </p>
                  </div>
                </div>
              </div>
            )}

            {stressData && stressData.scenarios.length > 0 && (
              <div className="flex flex-col gap-3">
                <p className="text-sm font-medium text-zinc-500 dark:text-zinc-400">
                  Historical Stress Scenarios
                </p>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {stressData.scenarios.map((s) => (
                    <StressScenarioCard key={s.scenario_name} scenario={s} />
                  ))}
                </div>
                <p className="text-xs text-zinc-400">{stressData.disclaimer}</p>
              </div>
            )}
          </section>
        )}
        {portfolio && portfolio.holdings.length > 0 && riskLoading && !riskData && (
          <p className="text-sm text-zinc-400">Loading risk analysis...</p>
        )}

        {/* Account Settings */}
        <section className="flex flex-col gap-4 border-t border-zinc-300 pt-6 dark:border-zinc-600">
          <h2 className="text-xl font-bold dark:text-zinc-200">Account</h2>

          <div className={sectionCls}>
            <div className="text-sm text-zinc-500 dark:text-zinc-400">
              Email:{" "}
              <span className="text-zinc-900 dark:text-white">
                {session.user.email}
              </span>
            </div>
          </div>

          <form className={sectionCls} onSubmit={saveName}>
            <h3 className="text-base font-semibold dark:text-zinc-200">Name</h3>
            <div>
              <label className={labelCls}>Display name</label>
              <input
                className={inputCls}
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>
            <div className="flex items-center gap-3">
              <button
                type="submit"
                disabled={profileStatus.kind === "saving"}
                className={btnCls}
              >
                {profileStatus.kind === "saving" ? "Saving..." : "Save"}
              </button>
              <StatusLine status={profileStatus} />
            </div>
          </form>

          <form className={sectionCls} onSubmit={savePassword}>
            <h3 className="text-base font-semibold dark:text-zinc-200">
              Change Password
            </h3>
            <div>
              <label className={labelCls}>Current password</label>
              <input
                className={inputCls}
                type="password"
                value={currentPw}
                onChange={(e) => setCurrentPw(e.target.value)}
                required
                autoComplete="current-password"
              />
            </div>
            <div>
              <label className={labelCls}>New password (8+ characters)</label>
              <input
                className={inputCls}
                type="password"
                value={newPw}
                onChange={(e) => setNewPw(e.target.value)}
                required
                autoComplete="new-password"
                minLength={8}
              />
            </div>
            <div className="flex items-center gap-3">
              <button
                type="submit"
                disabled={pwStatus.kind === "saving"}
                className={btnCls}
              >
                {pwStatus.kind === "saving" ? "Changing..." : "Change Password"}
              </button>
              <StatusLine status={pwStatus} />
            </div>
          </form>
        </section>
      </main>
    </div>
  );
}
