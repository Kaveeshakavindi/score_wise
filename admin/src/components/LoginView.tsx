import { FormEvent, useState } from "react";
import { ApiError, login } from "../api";

export function LoginView({ onLoggedIn }: { onLoggedIn: () => void }) {
  const [nickname, setNickname] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(nickname, password);
      onLoggedIn();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="centered-page">
      <form className="card login-card" onSubmit={handleSubmit}>
        <h1>ScoreWise Admin</h1>
        <p className="subtle">Sign in with your ScoreWise account to manage syllabus documents.</p>

        <label>
          Nickname
          <input value={nickname} onChange={(e) => setNickname(e.target.value)} autoFocus required />
        </label>

        <label>
          Password
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </label>

        {error && <p className="error-text">{error}</p>}

        <button type="submit" disabled={submitting}>
          {submitting ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
