"use client";

import Link from "next/link";
import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { CheckCircle2, KeyRound } from "lucide-react";
import { DecorativeBlobs } from "../_components/DecorativeBlobs";
import { Nav } from "../_components/Nav";
import { AuthCard, AuthField, AUTH_SUBMIT } from "../_components/AuthCard";

// Wired to POST /api/auth/reset-password with the `token` this page was
// opened with (from the link in the reset email). On success, every session
// the account had before the reset is already revoked server-side — this
// page just points the student at /login to start a fresh one.
export default function ResetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ResetPasswordForm />
    </Suspense>
  );
}

function ResetPasswordForm() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      setError("Those passwords don't match.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/reset-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, newPassword }),
      });
      if (!res.ok) {
        throw new Error((await res.json()).error ?? `Request failed (${res.status})`);
      }
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (!token) {
    return (
      <>
        <Nav />
        <main className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-6 py-28">
          <DecorativeBlobs />
          <AuthCard icon={<KeyRound size={20} strokeWidth={2} />} eyebrow="Reset your password" title="Invalid link" subtitle="This reset link is missing its token.">
            <p className="text-center text-sm text-text-muted">
              Request a new one from the{" "}
              <Link href="/forgot-password" className="font-medium text-text-dark underline underline-offset-2">
                forgot password
              </Link>{" "}
              page.
            </p>
          </AuthCard>
        </main>
      </>
    );
  }

  return (
    <>
      <Nav />
      <main className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-6 py-28">
        <DecorativeBlobs />
        <AuthCard
          icon={done ? <CheckCircle2 size={20} strokeWidth={2} /> : <KeyRound size={20} strokeWidth={2} />}
          eyebrow="Reset your password"
          title={done ? "Password updated" : "Set a new password"}
          subtitle={done ? "You're signed out everywhere — log in with your new password." : "Choose a new password for your account."}
        >
          {done ? (
            <Link href="/login" className={`${AUTH_SUBMIT} block w-full text-center`}>
              Log in
            </Link>
          ) : (
            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              <AuthField
                label="New password"
                type="password"
                value={newPassword}
                onChange={setNewPassword}
                placeholder="At least 8 characters"
                minLength={8}
                autoComplete="new-password"
                required
              />
              <AuthField
                label="Confirm password"
                type="password"
                value={confirmPassword}
                onChange={setConfirmPassword}
                placeholder="Re-enter your new password"
                minLength={8}
                autoComplete="new-password"
                required
              />

              <button type="submit" disabled={submitting} className={`${AUTH_SUBMIT} mt-2 disabled:opacity-60`}>
                {submitting ? "Updating…" : "Update password"}
              </button>

              {error && (
                <p className="rounded-2xl bg-coral/15 px-4 py-3 text-center text-sm text-text-dark" role="alert">
                  {error}
                </p>
              )}
            </form>
          )}
        </AuthCard>
      </main>
    </>
  );
}
