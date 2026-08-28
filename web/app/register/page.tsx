"use client";

import Link from "next/link";
import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { UserPlus } from "lucide-react";
import { DecorativeBlobs } from "../_components/DecorativeBlobs";
import { Nav } from "../_components/Nav";
import { AuthCard, AuthField, AUTH_SUBMIT } from "../_components/AuthCard";

// Wired to POST /api/auth/register, which only creates the account — it
// does not start a session. On success this sends the student to /login to
// sign in with the credentials they just chose, carrying `next` through so
// the eventual login still lands them wherever they were originally headed.
export default function RegisterPage() {
  return (
    <Suspense fallback={null}>
      <RegisterForm />
    </Suspense>
  );
}

function RegisterForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get("next") ?? "/dashboard";

  const [name, setName] = useState("");
  const [nickname, setNickname] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [age, setAge] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, nickname, password, age: Number(age), email }),
      });
      if (!res.ok) {
        throw new Error((await res.json()).error ?? `Request failed (${res.status})`);
      }
      router.push(`/login?next=${encodeURIComponent(next)}`);
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
          icon={<UserPlus size={20} strokeWidth={2} />}
          eyebrow="Get started"
          title="Create an account"
          subtitle="Set up a profile to track your practice and tutoring."
        >
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <AuthField label="Name" type="text" value={name} onChange={setName} placeholder="Full name" required />
            <AuthField
              label="Email"
              type="email"
              value={email}
              onChange={setEmail}
              placeholder="you@example.com"
              autoComplete="email"
              required
            />
            <AuthField
              label="Nickname"
              type="text"
              value={nickname}
              onChange={setNickname}
              placeholder="Letters, numbers, underscores"
              pattern="^[a-zA-Z0-9_]{3,32}$"
              title="3-32 characters: letters, numbers, and underscores only"
              autoComplete="username"
              required
            />
            <AuthField
              label="Password"
              type="password"
              value={password}
              onChange={setPassword}
              placeholder="At least 8 characters"
              minLength={8}
              autoComplete="new-password"
              required
            />
            <AuthField
              label="Age"
              type="number"
              value={age}
              onChange={setAge}
              placeholder="13-120"
              min={13}
              max={120}
              required
            />

            <button type="submit" disabled={submitting} className={`${AUTH_SUBMIT} mt-2 disabled:opacity-60`}>
              {submitting ? "Creating account…" : "Create account"}
            </button>

            {error && (
              <p className="rounded-2xl bg-coral/15 px-4 py-3 text-center text-sm text-text-dark" role="alert">
                {error}
              </p>
            )}
          </form>

          <p className="mt-6 text-center text-sm text-text-muted">
            Already have an account?{" "}
            <Link
              href={`/login?next=${encodeURIComponent(next)}`}
              className="font-medium text-text-dark underline underline-offset-2"
            >
              Log in
            </Link>
          </p>
        </AuthCard>
      </main>
    </>
  );
}
