"use client";

import Link from "next/link";
import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { LogIn } from "lucide-react";
import { DecorativeBlobs } from "../_components/DecorativeBlobs";
import { Nav } from "../_components/Nav";
import { AuthCard, AuthField, AUTH_SUBMIT } from "../_components/AuthCard";

// Wired to POST /api/auth/login (a Next.js Route Handler, not the FastAPI
// backend directly — it sets the httpOnly session cookies and never returns
// the token pair to this component). Lands on /dashboard by default; `next`
// overrides that when middleware.ts bounced the visitor from a specific
// protected page (e.g. /exam), so a successful login still lands them back
// where they were originally headed.
export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get("next") ?? "/dashboard";

  const [nickname, setNickname] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nickname, password }),
      });
      if (!res.ok) {
        throw new Error((await res.json()).error ?? `Request failed (${res.status})`);
      }
      router.push(next);
      router.refresh();
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
          icon={<LogIn size={20} strokeWidth={2} />}
          eyebrow="Welcome back"
          title="Log in"
          subtitle="Pick up your practice where you left off."
        >
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <AuthField
              label="Nickname"
              type="text"
              value={nickname}
              onChange={setNickname}
              placeholder="e.g. study_sam"
              autoComplete="username"
              required
            />
            <AuthField
              label="Password"
              type="password"
              value={password}
              onChange={setPassword}
              placeholder="••••••••"
              autoComplete="current-password"
              required
            />
            <Link href="/forgot-password" className="self-end text-sm text-text-muted underline underline-offset-2 hover:text-text-dark">
              Forgot password?
            </Link>

            <button type="submit" disabled={submitting} className={`${AUTH_SUBMIT} mt-2 disabled:opacity-60`}>
              {submitting ? "Logging in…" : "Log in"}
            </button>

            {error && (
              <p className="rounded-2xl bg-coral/15 px-4 py-3 text-center text-sm text-text-dark" role="alert">
                {error}
              </p>
            )}
          </form>

          <p className="mt-6 text-center text-sm text-text-muted">
            New here?{" "}
            <Link
              href={`/register?next=${encodeURIComponent(next)}`}
              className="font-medium text-text-dark underline underline-offset-2"
            >
              Create an account
            </Link>
          </p>
        </AuthCard>
      </main>
    </>
  );
}
