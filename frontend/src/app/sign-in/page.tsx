"use client"

import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { Suspense, useState } from "react"

import { authClient } from "@/lib/auth-client"

function SignInForm() {
  const router = useRouter()
  const params = useSearchParams()
  const callback = params.get("redirect") ?? "/"
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setPending(true)
    const { error } = await authClient.signIn.email({ email, password })
    setPending(false)
    if (error) {
      setError(error.message ?? "Sign in failed")
      return
    }
    router.push(callback)
    router.refresh()
  }

  return (
    <>
      <h1 className="text-xl font-semibold dark:text-white">Sign In</h1>
      <form onSubmit={onSubmit} className="mt-6 space-y-3">
        <input
          type="email"
          required
          autoComplete="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-white"
        />
        <input
          type="password"
          required
          autoComplete="current-password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-white"
        />
        {error && (
          <p className="text-xs text-red-600 dark:text-red-400">{error}</p>
        )}
        <button
          type="submit"
          disabled={pending}
          className="w-full rounded-lg bg-zinc-900 px-3 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
        >
          {pending ? "Signing in..." : "Sign In"}
        </button>
      </form>
      <p className="mt-4 text-center text-xs text-zinc-500 dark:text-zinc-400">
        Don&apos;t have an account?{" "}
        <Link
          href={`/sign-up${callback !== "/" ? `?redirect=${encodeURIComponent(callback)}` : ""}`}
          className="underline"
        >
          Sign Up
        </Link>
      </p>
    </>
  )
}

export default function SignIn() {
  return (
    <main className="mx-auto max-w-sm p-4 pt-12">
      <Suspense>
        <SignInForm />
      </Suspense>
    </main>
  )
}
