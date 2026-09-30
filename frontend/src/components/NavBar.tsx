import { Link, useLocation } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { Logo } from "./Logo";

export function NavBar() {
  const { user, logout } = useAuth();
  const location = useLocation();

  return (
    <header
      style={{
        position: "sticky",
        top: 0,
        zIndex: 20,
        background: "color-mix(in srgb, var(--surface) 72%, transparent)",
        backdropFilter: "var(--nav-blur)",
        WebkitBackdropFilter: "var(--nav-blur)",
        borderBottom: "1px solid var(--border)",
      }}
    >
      <div className="container row" style={{ height: 56, justifyContent: "space-between" }}>
        <Link to="/" className="row" style={{ gap: 8, color: "var(--text)" }}>
          <Logo size={26} />
          <strong style={{ fontSize: 15, letterSpacing: "-0.01em" }}>DataMind</strong>
        </Link>

        <nav className="row" style={{ gap: 4 }}>
          <Link
            to="/onboarding"
            className="btn btn-ghost"
            style={{
              background: location.pathname.startsWith("/onboarding") ? "var(--accent-soft)" : "transparent",
            }}
          >
            Upload data
          </Link>
          <Link
            to="/dashboard"
            className="btn btn-ghost"
            style={{
              background: location.pathname.startsWith("/dashboard") ? "var(--accent-soft)" : "transparent",
            }}
          >
            Dashboard
          </Link>
        </nav>

        <div className="row" style={{ gap: 10 }}>
          {user?.picture ? (
            <img
              src={user.picture}
              alt={user.name}
              style={{ width: 28, height: 28, borderRadius: "50%" }}
              referrerPolicy="no-referrer"
            />
          ) : (
            <span
              className="row"
              style={{
                width: 28,
                height: 28,
                borderRadius: "50%",
                background: "var(--accent-soft)",
                color: "var(--accent)",
                justifyContent: "center",
                fontSize: 12,
                fontWeight: 700,
              }}
            >
              {user?.name?.[0]?.toUpperCase() || "?"}
            </span>
          )}
          <button className="btn btn-ghost" onClick={logout}>
            Sign out
          </button>
        </div>
      </div>
    </header>
  );
}
