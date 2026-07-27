"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { authClient } from "@/lib/auth-client";
import { Navbar } from "@/components/Navbar";

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

// Rendered only once the session has loaded, so useState initializers below
// see the real values (no sync-from-prop effect needed).
function AccountForms({ email, initialName }: { email: string; initialName: string }) {
  const router = useRouter();

  const [name, setName] = useState(initialName);
  const [profileStatus, setProfileStatus] = useState<Status>({ kind: "idle" });

  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [pwStatus, setPwStatus] = useState<Status>({ kind: "idle" });

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

  return (
    <>
      <div className={sectionCls}>
        <div className="text-sm text-zinc-500 dark:text-zinc-400">
          Email: <span className="text-zinc-900 dark:text-white">{email}</span>
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
    </>
  );
}

export default function AccountPage() {
  const router = useRouter();
  const { data: session, isPending } = authClient.useSession();

  useEffect(() => {
    if (!isPending && !session) {
      router.push("/sign-in?redirect=/account");
    }
  }, [isPending, session, router]);

  if (isPending || !session) return null;

  return (
    <div className="flex flex-col flex-1 items-center bg-zinc-50 font-sans dark:bg-zinc-950">
      <Navbar />
      <main className="flex flex-1 w-full max-w-3xl flex-col gap-6 py-8 px-4 sm:py-12 sm:px-8">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold tracking-tight dark:text-white">
            Account
          </h1>
          <Link
            href="/dashboard"
            className="text-sm text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200"
          >
            ← Back to Dashboard
          </Link>
        </div>

        <AccountForms
          email={session.user.email}
          initialName={session.user.name || ""}
        />
      </main>
    </div>
  );
}
