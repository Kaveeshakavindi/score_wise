"use client";

import Link from "next/link";
import { useState } from "react";
import { KeyRound, MailCheck } from "lucide-react";
import { DecorativeBlobs } from "../_components/DecorativeBlobs";
import { Nav } from "../_components/Nav";
import { AuthCard, AuthField, AUTH_SUBMIT } from "../_components/AuthCard";

// Wired to POST /api/auth/forgot-password. The backend always returns the
// same message regardless of whether the email has an account
// (anti-enumeration) — this page just displays whatever it gets back, no
// enumeration logic of its own.
export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/forgot-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? `Request failed (${res.status})`);
      setMessage(data.message ?? "If an account exists for that email, a reset link has been sent.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <Nav />
      <main className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-6 py-28">
        <DecorativeBlobs />
        <AuthCard
          icon={message ? <MailCheck size={20} strokeWidth={2} /> : <KeyRound size={20} strokeWidth={2} />}
          eyebrow="Reset your password"
          title="Forgot password?"
          subtitle="Enter the email on your account and we'll send you a reset link."
        >
          {message ? (
            <p className="rounded-2xl bg-sage/60 px-4 py-3 text-center text-sm text-text-dark">{message}</p>
          ) : (
            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              <AuthField
                label="Email"
                type="email"
                value={email}
                onChange={setEmail}
                placeholder="you@example.com"
                autoComplete="email"
                required
              />

              <button type="submit" disabled={submitting} className={`${AUTH_SUBMIT} mt-2 disabled:opacity-60`}>
                {submitting ? "Sending…" : "Send reset link"}
              </button>

              {error && (
                <p className="rounded-2xl bg-coral/15 px-4 py-3 text-center text-sm text-text-dark" role="alert">
                  {error}
                </p>
              )}
            </form>
          )}

          <p className="mt-6 text-center text-sm text-text-muted">
            <Link href="/login" className="font-medium text-text-dark underline underline-offset-2">
              Back to log in
            </Link>
          </p>
        </AuthCard>
      </main>
    </>
  );
}
