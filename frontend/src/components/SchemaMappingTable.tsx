import type { ColumnMapping } from "../lib/types";

const TYPE_OPTIONS = ["VARCHAR", "INTEGER", "FLOAT", "NUMBER(18,2)", "BOOLEAN", "DATE", "TIMESTAMP_NTZ"];

function confidencePillClass(confidence: number): string {
  if (confidence >= 0.85) return "pill-success";
  if (confidence >= 0.6) return "pill-warning";
  return "pill-danger";
}

export function SchemaMappingTable({
  columns,
  onChange,
}: {
  columns: ColumnMapping[];
  onChange: (columns: ColumnMapping[]) => void;
}) {
  function update(id: string, patch: Partial<ColumnMapping>) {
    onChange(
      columns.map((c) => (c.id === id ? { ...c, ...patch, source: "USER_MODIFIED" as const } : c))
    );
  }

  return (
    <div className="scroll-thin" style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13.5 }}>
        <thead>
          <tr style={{ textAlign: "left", color: "var(--text-secondary)", fontSize: 12 }}>
            <th style={{ padding: "8px 10px" }}>Raw column</th>
            <th style={{ padding: "8px 10px" }}>AI interpretation</th>
            <th style={{ padding: "8px 10px" }}>Snowflake column</th>
            <th style={{ padding: "8px 10px" }}>Type</th>
            <th style={{ padding: "8px 10px", textAlign: "center" }}>Nullable</th>
            <th style={{ padding: "8px 10px", textAlign: "center" }}>Key</th>
            <th style={{ padding: "8px 10px", textAlign: "center" }}>Confidence</th>
            <th style={{ padding: "8px 10px", textAlign: "center" }}>Include</th>
          </tr>
        </thead>
        <tbody>
          {columns.map((col) => (
            <tr
              key={col.id}
              style={{
                borderTop: "1px solid var(--border)",
                opacity: col.include ? 1 : 0.45,
              }}
            >
              <td style={{ padding: "10px" }}>
                <code style={{ fontFamily: "var(--font-mono)", fontSize: 12.5 }}>{col.source_column}</code>
              </td>
              <td style={{ padding: "10px", color: "var(--text-secondary)" }}>
                {col.semantic_type || "—"}
                {col.source === "USER_MODIFIED" && (
                  <div>
                    <span className="pill pill-accent" style={{ marginTop: 4, fontSize: 10 }}>
                      User modified
                    </span>
                  </div>
                )}
              </td>
              <td style={{ padding: "10px" }}>
                <input
                  className="input"
                  style={{ padding: "6px 10px", minWidth: 140 }}
                  value={col.target_column}
                  disabled={!col.include}
                  onChange={(e) => update(col.id, { target_column: e.target.value })}
                />
              </td>
              <td style={{ padding: "10px" }}>
                <select
                  className="select"
                  style={{ padding: "6px 8px", minWidth: 120 }}
                  value={col.target_type}
                  disabled={!col.include}
                  onChange={(e) => update(col.id, { target_type: e.target.value })}
                >
                  {TYPE_OPTIONS.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </td>
              <td style={{ padding: "10px", textAlign: "center" }}>
                <input
                  type="checkbox"
                  checked={col.nullable}
                  disabled={!col.include}
                  onChange={(e) => update(col.id, { nullable: e.target.checked })}
                />
              </td>
              <td style={{ padding: "10px", textAlign: "center" }}>
                <div className="row" style={{ gap: 6, justifyContent: "center" }}>
                  <label title="Primary key" className="row" style={{ gap: 3, fontSize: 11 }}>
                    <input
                      type="checkbox"
                      checked={col.primary_key_candidate}
                      disabled={!col.include}
                      onChange={(e) => update(col.id, { primary_key_candidate: e.target.checked })}
                    />
                    PK
                  </label>
                  <label title="Foreign key" className="row" style={{ gap: 3, fontSize: 11 }}>
                    <input
                      type="checkbox"
                      checked={col.foreign_key_candidate}
                      disabled={!col.include}
                      onChange={(e) => update(col.id, { foreign_key_candidate: e.target.checked })}
                    />
                    FK
                  </label>
                </div>
              </td>
              <td style={{ padding: "10px", textAlign: "center" }}>
                <span className={`pill ${confidencePillClass(col.confidence)}`}>
                  {Math.round(col.confidence * 100)}%
                </span>
              </td>
              <td style={{ padding: "10px", textAlign: "center" }}>
                <input
                  type="checkbox"
                  checked={col.include}
                  onChange={(e) => update(col.id, { include: e.target.checked })}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
