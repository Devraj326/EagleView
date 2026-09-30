export function AgentLogPanel({ log, onClear }: { log: string[]; onClear: () => void }) {
  if (log.length === 0) return null;
  return (
    <details className="card" style={{ marginTop: 28, padding: "12px 18px" }}>
      <summary style={{ cursor: "pointer", fontWeight: 560, fontSize: 13.5 }}>
        Processing activity ({log.length})
      </summary>
      <pre
        className="scroll-thin"
        style={{
          marginTop: 12,
          fontSize: 12,
          fontFamily: "var(--font-mono)",
          color: "var(--text-secondary)",
          whiteSpace: "pre-wrap",
          maxHeight: 260,
          overflowY: "auto",
        }}
      >
        {log.join("\n")}
      </pre>
      <button className="btn btn-secondary" style={{ marginTop: 8 }} onClick={onClear}>
        Clear log
      </button>
    </details>
  );
}

