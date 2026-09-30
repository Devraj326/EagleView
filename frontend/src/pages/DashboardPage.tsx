import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { NavBar } from "../components/NavBar";
import { ResultView } from "../components/ResultView";
import { Spinner } from "../components/Spinner";
import { ApiError, api } from "../lib/api";
import type { ChatTurn, ReadyDomain } from "../lib/types";
import { AgentLogPanel } from "./OnboardingPage";

const SUGGESTIONS = [
  "What was our total revenue last month?",
  "Which products are below their reorder level?",
  "Show me the top 10 customers by spending.",
  "Which deliveries were delayed?",
];

let turnCounter = 0;
function nextId() {
  turnCounter += 1;
  return `turn_${turnCounter}_${Date.now()}`;
}

export function DashboardPage() {
  const [domains, setDomains] = useState<ReadyDomain[]>([]);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [agentLog, setAgentLog] = useState<string[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api
      .listDatasets()
      .then((r) => setDomains(r.domains))
      .catch(() => {});
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns]);

  async function submit(q: string) {
    const question = q.trim();
    if (!question || asking) return;

    setQuestion("");
    setAsking(true);
    const pendingId = nextId();
    setTurns((prev) => [
      ...prev,
      { id: nextId(), role: "user", question },
      { id: pendingId, role: "assistant", pending: true },
    ]);

    try {
      const response = await api.ask(question, sessionId);
      setSessionId(response.session_id);
      if (response.agent_log?.length) setAgentLog((prev) => [...prev, ...response.agent_log]);
      setTurns((prev) =>
        prev.map((t) => (t.id === pendingId ? { ...t, pending: false, response } : t))
      );
    } catch (e) {
      const message = e instanceof ApiError ? e.message : "Something went wrong answering that.";
      setTurns((prev) => (prev.map((t) => (t.id === pendingId ? { ...t, pending: false, error: message } : t))));
    } finally {
      setAsking(false);
    }
  }

  function newConversation() {
    setTurns([]);
    setSessionId(null);
  }

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <NavBar />
      <div
        className="container dashboard-layout"
        style={{ flex: 1, display: "flex", gap: 24, paddingTop: 24, paddingBottom: 24 }}
      >
        <aside className="dashboard-sidebar" style={{ width: 240, flexShrink: 0 }}>
          <div className="row" style={{ justifyContent: "space-between", marginBottom: 12 }}>
            <h3 style={{ fontSize: 12, color: "var(--text-secondary)", fontWeight: 600 }}>MY DOMAINS</h3>
            <Link to="/onboarding" className="btn-ghost btn" style={{ padding: "2px 8px", fontSize: 12 }}>
              + Add
            </Link>
          </div>
          {domains.length === 0 ? (
            <p style={{ fontSize: 13, color: "var(--text-tertiary)" }}>
              No data ready yet.{" "}
              <Link to="/onboarding" style={{ color: "var(--accent)" }}>
                Upload one
              </Link>
              .
            </p>
          ) : (
            <div className="stack" style={{ gap: 6 }}>
              {domains.map((d) => (
                <div key={d.agent_key} className="card" style={{ padding: "10px 12px", boxShadow: "none" }}>
                  <div style={{ fontSize: 13, fontWeight: 560 }}>{d.agent_label}</div>
                  <div style={{ fontSize: 11.5, color: "var(--text-secondary)" }}>
                    {d.table_name} · {d.row_count.toLocaleString()} rows
                  </div>
                </div>
              ))}
            </div>
          )}

          {turns.length > 0 && (
            <button
              className="btn btn-secondary"
              style={{ width: "100%", marginTop: 20, fontSize: 13 }}
              onClick={newConversation}
            >
              New conversation
            </button>
          )}

          <div style={{ marginTop: 20 }}>
            <AgentLogPanel log={agentLog} onClear={() => setAgentLog([])} />
          </div>
        </aside>

        <main style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
          <div ref={scrollRef} className="scroll-thin stack" style={{ flex: 1, gap: 18, overflowY: "auto", paddingBottom: 8 }}>
            {turns.length === 0 && (
              <div className="card fade-in-up" style={{ padding: 32 }}>
                <h2 style={{ fontSize: 18, fontWeight: 620 }}>Ask your data anything</h2>
                <p style={{ color: "var(--text-secondary)", fontSize: 14, marginTop: 6 }}>
                  Ask analytical questions, or investigate a specific order, customer, product, or shipment
                  — in plain English. Each question is dispatched to the domain agent(s) that own the
                  relevant data.
                </p>
                <div className="row" style={{ gap: 8, flexWrap: "wrap", marginTop: 16 }}>
                  {SUGGESTIONS.map((s) => (
                    <button key={s} className="btn btn-secondary" style={{ fontSize: 13 }} onClick={() => submit(s)}>
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {turns.map((turn) =>
              turn.role === "user" ? (
                <div key={turn.id} style={{ alignSelf: "flex-end", maxWidth: "72%" }}>
                  <div
                    className="fade-in-up"
                    style={{
                      background: "var(--accent)",
                      color: "white",
                      padding: "10px 16px",
                      borderRadius: "var(--radius-lg)",
                      borderBottomRightRadius: 4,
                      fontSize: 14.5,
                    }}
                  >
                    {turn.question}
                  </div>
                </div>
              ) : (
                <div key={turn.id} style={{ alignSelf: "flex-start", maxWidth: "88%", width: "100%" }}>
                  <div
                    className="card fade-in-up"
                    style={{ padding: "16px 20px", borderBottomLeftRadius: 4 }}
                  >
                    {turn.pending && (
                      <div className="row" style={{ gap: 10 }}>
                        <Spinner size={16} />
                        <span style={{ fontSize: 13.5, color: "var(--text-secondary)" }}>
                          Consulting the relevant domain agent(s)… this can take a couple of minutes.
                        </span>
                      </div>
                    )}
                    {turn.error && <p style={{ color: "var(--danger)", fontSize: 14 }}>{turn.error}</p>}
                    {turn.response && <ResultView response={turn.response} />}
                  </div>
                </div>
              )
            )}
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              submit(question);
            }}
            className="row"
            style={{ gap: 10, marginTop: 16 }}
          >
            <input
              className="input"
              placeholder="Ask about your data…"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              disabled={asking}
              style={{ padding: "13px 16px", fontSize: 14.5 }}
            />
            <button className="btn btn-primary" type="submit" disabled={asking || !question.trim()}>
              {asking ? <Spinner size={14} color="white" /> : "Ask"}
            </button>
          </form>
        </main>
      </div>
    </div>
  );
}
