import React, { useEffect, useState } from "react";
const CONNECTED_APP =
  "https://preview-f60ac8b0bd88be45.up.railway.app/?entry=command-center";
const PREVIEW_HOST = "wildfirewatch-command-center.fancycreek1.chatgpt.site";

export default function OperatorGate({ children }) {
  const [auth, setAuth] = useState(null);
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    // The Sites host serves static assets; the complete Python app owns its
    // authenticated API, WebSocket connection, and camera monitoring UI.
    if (window.location.hostname === PREVIEW_HOST) {
      setAuth({ redirecting: true });
      window.location.replace(CONNECTED_APP);
      return;
    }
    fetch("/api/auth/status")
      .then((r) => r.json())
      .then(setAuth)
      .catch(() => setAuth({ required: false, preview: true }));
    const expired = () => setAuth({ required: true, authenticated: false });
    window.addEventListener("operator-session-expired", expired);
    return () =>
      window.removeEventListener("operator-session-expired", expired);
  }, []);
  async function login(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      const value = await response.json();
      if (!response.ok) throw Error(value.detail || "Sign-in failed");
      setPassword("");
      setAuth({ required: true, authenticated: true });
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  if (auth?.redirecting)
    return (
      <main className="operator-gate">
        <div className="panel" style={{ padding: 32, maxWidth: 480 }}>
          <h1>Opening the connected application…</h1>
          <p>
            The live camera feeds and trained detector run in the full
            WildfireWatch application.
          </p>
          <a href={CONNECTED_APP} target="_top">
            Open WildfireWatch with live monitoring →
          </a>
        </div>
      </main>
    );
  if (!auth)
    return (
      <main className="operator-gate">
        <p>Connecting to WildfireWatch…</p>
      </main>
    );
  if (!auth.required)
    return (
      <>
        {auth.preview && (
          <div className="operator-session">
            This address shows the interface preview.{" "}
            <a href="https://preview-f60ac8b0bd88be45.up.railway.app">
              Open the connected cloud application
            </a>{" "}
            · Operator password required; temporary Railway preview.
          </div>
        )}
        {children}
      </>
    );
  if (auth.authenticated)
    return (
      <>
        <div className="operator-session">
          Private operator session{" "}
          <button
            onClick={async () => {
              await fetch("/api/auth/logout", { method: "POST" });
              setAuth({ required: true, authenticated: false });
            }}
          >
            Sign out
          </button>
        </div>
        {children}
      </>
    );
  return (
    <main className="operator-gate">
      <form className="panel" onSubmit={login}>
        <span className="eyebrow">
          WildfireWatch · private research deployment
        </span>
        <h1>Operator sign-in</h1>
        <p>
          This installation contains photo evidence and review decisions. Enter
          the deployment's operator password to continue.
        </p>
        <label htmlFor="operator-password">Operator password</label>
        <input
          id="operator-password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          maxLength={256}
        />
        {error && <p role="alert">{error}</p>}
        <button className="primary" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
        <small>
          Research prototype. Not an official emergency reporting service.
        </small>
      </form>
    </main>
  );
}
