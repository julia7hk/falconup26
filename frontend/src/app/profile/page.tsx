"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { useEffect, useState } from "react"

import { authClient } from "@/lib/auth-client"

type Status =
  | { kind: "idle" }
  | { kind: "saving" }
  | { kind: "ok"; msg: string }
  | { kind: "err"; msg: string }

type Portfolio = {
  holdings: {
    id: number
    ticker: string
    name: string
    shares: number
    avg_cost: number
    cost_basis: number
    price: number | null
    market_value: number | null
    pnl: number | null
    pnl_percent: number | null
  }[]
  total_value: number
  total_cost: number
  total_pnl: number
  prices_complete: boolean
}

function StatusLine({ status }: { status: Status }) {
  if (status.kind === "idle" || status.kind === "saving") return null
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
  )
}

const sectionCls =
  "space-y-3 rounded-lg border border-zinc-200 p-5 dark:border-zinc-700"
const labelCls =
  "block text-sm text-zinc-500 dark:text-zinc-400"
const inputCls =
  "w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-white"
const btnCls =
  "rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"

export default function ProfilePage() {
  const router = useRouter()
  const { data: session, isPending } = authClient.useSession()

  const [name, setName] = useState(session?.user.name || "")
  const [profileStatus, setProfileStatus] = useState<Status>({ kind: "idle" })

  const [currentPw, setCurrentPw] = useState("")
  const [newPw, setNewPw] = useState("")
  const [pwStatus, setPwStatus] = useState<Status>({ kind: "idle" })

  const [portfolio, setPortfolio] = useState<Portfolio | null>(null)

  useEffect(() => {
    if (session) {
      fetch("/api/portfolio", { credentials: "include" })
        .then((res) => (res.ok ? res.json() : null))
        .then(setPortfolio)
        .catch(() => {})
    }
  }, [session])

  useEffect(() => {
    if (!isPending && !session) {
      router.push("/sign-in?redirect=/profile")
    }
  }, [isPending, session, router])

  if (isPending || !session) return null

  async function saveName(e: React.FormEvent) {
    e.preventDefault()
    setProfileStatus({ kind: "saving" })
    try {
      const { error } = await authClient.updateUser({ name })
      if (error) throw new Error(error.message ?? "Update failed")
      setProfileStatus({ kind: "ok", msg: "Name updated." })
      router.refresh()
    } catch (err) {
      setProfileStatus({
        kind: "err",
        msg: err instanceof Error ? err.message : "Update failed",
      })
    }
  }

  async function savePassword(e: React.FormEvent) {
    e.preventDefault()
    if (newPw.length < 8) {
      setPwStatus({ kind: "err", msg: "Password must be at least 8 characters." })
      return
    }
    setPwStatus({ kind: "saving" })
    try {
      const { error } = await authClient.changePassword({
        currentPassword: currentPw,
        newPassword: newPw,
      })
      if (error) throw new Error(error.message ?? "Change failed")
      setPwStatus({ kind: "ok", msg: "Password changed." })
      setCurrentPw("")
      setNewPw("")
    } catch (err) {
      setPwStatus({
        kind: "err",
        msg: err instanceof Error ? err.message : "Change failed",
      })
    }
  }

  const fmt = (n: number) =>
    n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })

  return (
    <div className="flex flex-col flex-1 items-center bg-zinc-50 font-sans dark:bg-zinc-950">
      <main className="flex flex-1 w-full max-w-6xl flex-col gap-6 py-12 px-8">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold tracking-tight dark:text-white">
            Profile
          </h1>
          <Link
            href="/"
            className="text-sm text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200"
          >
            ← Back
          </Link>
        </div>

        {/* Portfolio Summary */}
        {portfolio && portfolio.holdings.length > 0 && (
          <section className={sectionCls}>
            <h2 className="text-base font-semibold dark:text-zinc-200">
              Portfolio Summary
            </h2>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <p className={labelCls}>Holdings</p>
                <p className="text-xl font-semibold dark:text-white">
                  {portfolio.holdings.length}
                </p>
              </div>
              <div>
                <p className={labelCls}>Total Value</p>
                <p className="font-mono text-xl font-semibold dark:text-white">
                  ${fmt(portfolio.total_value)}
                </p>
              </div>
              <div>
                <p className={labelCls}>Total P&L</p>
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
            {!portfolio.prices_complete && (
              <p className="text-xs text-amber-600 dark:text-amber-400">
                Some prices unavailable — totals may be incomplete.
              </p>
            )}
            {/* Holdings list */}
            <div className="mt-2 space-y-1">
              {portfolio.holdings.map((h) => (
                <div
                  key={h.id}
                  className="flex items-center justify-between text-sm"
                >
                  <div>
                    <span className="font-mono font-medium dark:text-white">
                      {h.ticker}
                    </span>
                    <span className="ml-2 text-zinc-400">
                      {h.shares} shares @ ${h.avg_cost.toFixed(2)}
                    </span>
                  </div>
                  <div className="text-right">
                    {h.market_value !== null ? (
                      <span className="font-mono dark:text-zinc-200">
                        ${fmt(h.market_value)}
                      </span>
                    ) : (
                      <span className="text-zinc-400">—</span>
                    )}
                    {h.pnl !== null && (
                      <span
                        className={`ml-2 ${
                          h.pnl >= 0
                            ? "text-green-600 dark:text-green-400"
                            : "text-red-600 dark:text-red-400"
                        }`}
                      >
                        {h.pnl >= 0 ? "+" : ""}{h.pnl_percent!.toFixed(1)}%
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {portfolio && portfolio.holdings.length === 0 && (
          <section className={sectionCls}>
            <h2 className="text-base font-semibold dark:text-zinc-200">
              Portfolio Summary
            </h2>
            <p className="text-sm text-zinc-400">
              No holdings yet.{" "}
              <Link href="/" className="underline">
                Add your first holding
              </Link>
              .
            </p>
          </section>
        )}

        {/* Account Info */}
        <section className={sectionCls}>
          <h2 className="text-base font-semibold dark:text-zinc-200">Account</h2>
          <div className="text-sm text-zinc-500 dark:text-zinc-400">
            Email:{" "}
            <span className="text-zinc-900 dark:text-white">
              {session.user.email}
            </span>
          </div>
        </section>

        {/* Change Name */}
        <form className={sectionCls} onSubmit={saveName}>
          <h2 className="text-base font-semibold dark:text-zinc-200">Name</h2>
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

        {/* Change Password */}
        <form className={sectionCls} onSubmit={savePassword}>
          <h2 className="text-base font-semibold dark:text-zinc-200">
            Change Password
          </h2>
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
      </main>
    </div>
  )
}
