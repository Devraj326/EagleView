import { GoogleLogin } from "@react-oauth/google";
import { useState } from "react";
import { Navigate } from "react-router-dom";
import { Logo } from "../components/Logo";
import { Spinner } from "../components/Spinner";
import { useAuth } from "../lib/auth";

export function LoginPage() {
  const { user, loading, loginWithGoogle, loginWithDemo } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [signingIn, setSigningIn] = useState(false);
  const [demoId, setDemoId] = useState<string | null>(null);

  async function handleDemo(id: string) {
    setError(null);
    setDemoId(id);
    try {
      await loginWithDemo(id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Demo sign-in failed");
    } finally {
      setDemoId(null);
    }
  }

  if (!loading && user) {
    return <Navigate to="/onboarding" replace />;
  }

  return (
    <div
      className="row"
      style={{
        minHeight: "100vh",
        justifyContent: "center",
        alignItems: "center",
        background:
          "radial-gradient(1200px 600px at 50% -10%, color-mix(in srgb, var(--accent) 14%, transparent), transparent), var(--bg)",
      }}
    >
      <div
        className="card fade-in-up"
        style={{ width: 400, padding: "40px 36px", textAlign: "center" }}
      >
        <div style={{ display: "flex", justifyContent: "center", marginBottom: 20 }}>
          <Logo size={56} />
        </div>
        <h1 style={{ fontSize: 24, fontWeight: 640, letterSpacing: "-0.02em" }}>
          Welcome to DataMind
        </h1>
        <p style={{ color: "var(--text-secondary)", fontSize: 14, marginTop: 8, lineHeight: 1.5 }}>
          Upload your business data, let AI understand it, and ask questions in plain English.
        </p>

        <div style={{ marginTop: 28, display: "flex", justifyContent: "center" }}>
          <GoogleLogin
            onSuccess={async (credentialResponse) => {
              setError(null);
              setSigningIn(true);
              try {
                if (!credentialResponse.credential) throw new Error("No credential returned");
                await loginWithGoogle(credentialResponse.credential);
              } catch (e) {
                setError(e instanceof Error ? e.message : "Sign-in failed");
              } finally {
                setSigningIn(false);
              }
            }}
            onError={() => setError("Google sign-in failed. Please try again.")}
            theme="outline"
            shape="pill"
          />
        </div>

        {signingIn && (
          <p style={{ marginTop: 14, fontSize: 13, color: "var(--text-secondary)" }}>Signing you in…</p>
        )}
        {error && (
          <p style={{ marginTop: 14, fontSize: 13, color: "var(--danger)" }}>{error}</p>
        )}

        <div className="row" style={{ gap: 10, margin: "22px 0 16px" }}>
          <div style={{ flex: 1, height: 1, background: "var(--border)" }} />
          <span style={{ fontSize: 11, color: "var(--text-tertiary)" }}>OR, FOR DEMO / TESTING</span>
          <div style={{ flex: 1, height: 1, background: "var(--border)" }} />
        </div>

        <div className="row" style={{ gap: 10, justifyContent: "center" }}>
          <button
            className="btn btn-secondary"
            style={{ flex: 1 }}
            disabled={demoId !== null}
            onClick={() => handleDemo("demo-a")}
          >
            {demoId === "demo-a" ? <Spinner size={14} /> : "Demo User A"}
          </button>
          <button
            className="btn btn-secondary"
            style={{ flex: 1 }}
            disabled={demoId !== null}
            onClick={() => handleDemo("demo-b")}
          >
            {demoId === "demo-b" ? <Spinner size={14} /> : "Demo User B"}
          </button>
        </div>
        <p style={{ marginTop: 10, fontSize: 11.5, color: "var(--text-tertiary)" }}>
          Two fixed demo accounts, fully isolated from each other just like real users.
        </p>
      </div>
    </div>
  );
}
