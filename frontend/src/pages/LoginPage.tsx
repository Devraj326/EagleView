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
    try { await loginWithDemo(id); }
    catch (e) { setError(e instanceof Error ? e.message : "Demo sign-in failed"); }
    finally { setDemoId(null); }
  }
  if (!loading && user) return <Navigate to="/onboarding" replace />;

  return (
    <div className="login-page">
      <header className="login-header">
        <a className="brand" href="/"><Logo size={28} /><span>Eagle View</span></a>
      </header>
      <main className="login-layout">
        <section className="login-panel" aria-labelledby="sign-in-title">
          <h1 id="sign-in-title">Sign in to Eagle View</h1>
          <p className="panel-description">A workspace for your data and questions.</p>
          {import.meta.env.VITE_GOOGLE_CLIENT_ID ? (
            <div className="google-login"><GoogleLogin
              onSuccess={async (response) => {
                setError(null); setSigningIn(true);
                try {
                  if (!response.credential) throw new Error("No credential returned");
                  await loginWithGoogle(response.credential);
                } catch (e) { setError(e instanceof Error ? e.message : "Sign-in failed"); }
                finally { setSigningIn(false); }
              }}
              onError={() => setError("Google sign-in failed. Please try again.")}
              theme="outline" shape="rectangular"
            /></div>
          ) : (
            <button
              type="button"
              className="google-login google-sign-in"
              onClick={() => setError("Google sign-in is temporarily unavailable. Please use a demo account.")}
            >
              <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
                <path fill="#4285F4" d="M43.6 24.5c0-1.4-.1-2.8-.4-4.1H24v7.8h11c-.5 2.5-1.9 4.6-4.1 6v5h6.6c3.9-3.6 6.1-8.7 6.1-14.7Z" />
                <path fill="#34A853" d="M24 44c5.5 0 10.1-1.8 13.5-4.9l-6.6-5c-1.8 1.2-4.1 1.9-6.9 1.9-5.3 0-9.8-3.6-11.4-8.4H5.8v5.2C9.2 39.4 16.1 44 24 44Z" />
                <path fill="#FBBC05" d="M12.6 27.6a12 12 0 0 1 0-7.2v-5.2H5.8a20 20 0 0 0 0 17.6l6.8-5.2Z" />
                <path fill="#EA4335" d="M24 12c3 0 5.7 1 7.8 3l5.8-5.8A19.5 19.5 0 0 0 24 4C16.1 4 9.2 8.6 5.8 15.2l6.8 5.2C14.2 15.6 18.7 12 24 12Z" />
              </svg>
              Sign in with Google
            </button>
          )}
          {signingIn && <p className="login-status" role="status">Signing you in…</p>}
          {error && <p className="login-error" role="alert">{error}</p>}
          <div className="demo-divider"><span>or try a demo</span></div>
          <div className="demo-accounts">
            <button className="btn btn-secondary" disabled={demoId !== null || signingIn} onClick={() => handleDemo("demo-a")}>
              {demoId === "demo-a" ? <Spinner size={16} /> : "Workspace A"}
            </button>
            <button className="btn btn-secondary" disabled={demoId !== null || signingIn} onClick={() => handleDemo("demo-b")}>
              {demoId === "demo-b" ? <Spinner size={16} /> : "Workspace B"}
            </button>
          </div>
        </section>
      </main>
    </div>
  );
}
