import { useState, type CSSProperties, type FormEvent } from "react";

import { ApiError } from "../lib/api";
import { LogoMark } from "./icons";

interface LoginProps {
  onSubmit: (password: string) => Promise<void>;
}

const primaryButton: CSSProperties = {
  border: "none",
  background: "var(--accent)",
  color: "#0a0d10",
  borderRadius: 9,
  padding: "10px 16px",
  font: "600 13px 'Hanken Grotesque', sans-serif",
  cursor: "pointer",
  width: "100%",
};

export function Login({ onSubmit }: LoginProps) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (pending || !password) {
      return;
    }
    setPending(true);
    setError(null);
    try {
      await onSubmit(password);
      // On success the app re-renders into the authenticated view; nothing to do.
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : err instanceof Error ? err.message : "Login failed.";
      setError(message);
      setPassword("");
      setPending(false);
    }
  }

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg)", display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}>
      <form
        onSubmit={handleSubmit}
        style={{
          width: "100%",
          maxWidth: 340,
          background: "var(--bg-2)",
          border: "1px solid var(--line)",
          borderRadius: 14,
          padding: 28,
          boxShadow: "var(--card-shadow)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 18 }}>
          <div style={{ width: 30, height: 30, borderRadius: 8, background: "var(--accent)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <LogoMark />
          </div>
          <div className="num" style={{ fontSize: 18, fontWeight: 600, letterSpacing: "-0.02em" }}>
            BurnRate
          </div>
        </div>

        <label htmlFor="br-password" style={{ display: "block", fontSize: 12.5, color: "var(--text-2)", marginBottom: 6 }}>
          Password
        </label>
        <input
          id="br-password"
          className="br-input"
          type="password"
          autoFocus
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          disabled={pending}
          style={{ width: "100%", marginBottom: error ? 8 : 16 }}
        />

        {error ? (
          <div style={{ fontSize: 12.5, color: "var(--over)", marginBottom: 16, lineHeight: 1.5 }}>{error}</div>
        ) : null}

        <button type="submit" style={{ ...primaryButton, opacity: pending || !password ? 0.6 : 1 }} disabled={pending || !password}>
          {pending ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
