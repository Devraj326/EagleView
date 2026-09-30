import { Database, MessageSquare, LogOut } from "lucide-react";
import { Link, NavLink } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { Logo } from "./Logo";

export function NavBar() {
  const { user, logout } = useAuth();
  return (
    <header className="app-header">
      <div className="container app-nav">
        <Link to="/" className="brand">
          <Logo size={29} />
          <span>Eagle View</span>
        </Link>
        <nav aria-label="Workspace navigation" className="workspace-nav">
          <NavLink to="/onboarding" className="nav-link">
            <Database size={16} />Data
          </NavLink>
          <NavLink to="/dashboard" className="nav-link">
            <MessageSquare size={16} />Analysis
          </NavLink>
        </nav>
        <div className="nav-user">
          {user?.picture ? (
            <img src={user.picture} alt={user.name} className="user-avatar" referrerPolicy="no-referrer" />
          ) : (
            <span className="user-avatar">{user?.name?.[0]?.toUpperCase() || "?"}</span>
          )}
          <span className="user-name">{user?.name}</span>
          <button className="sign-out" onClick={logout} aria-label="Sign out" title="Sign out">
            <LogOut size={17} />
          </button>
        </div>
      </div>
    </header>
  );
}
