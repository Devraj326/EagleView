import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { QueryResponse } from "../lib/types";

const PIE_COLORS = [
  "var(--chart-series-1)",
  "var(--chart-series-2)",
  "var(--chart-series-3)",
  "var(--chart-series-4)",
  "var(--chart-series-5)",
  "var(--chart-series-6)",
];

function isNumeric(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

function firstNumericField(row: Record<string, unknown> | undefined): string | null {
  if (!row) return null;
  for (const [k, v] of Object.entries(row)) {
    if (isNumeric(v)) return k;
  }
  return null;
}

function KpiTile({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ textAlign: "center", padding: "20px 0" }}>
      <div style={{ fontSize: 40, fontWeight: 650, letterSpacing: "-0.02em", fontVariantNumeric: "tabular-nums" }}>
        {value}
      </div>
      <div style={{ color: "var(--text-secondary)", fontSize: 13, marginTop: 6 }}>{label}</div>
    </div>
  );
}

function Chart({ response }: { response: QueryResponse }) {
  const viz = response.visualization;
  const rows = response.result;
  if (!viz || rows.length === 0) return null;

  if (viz.type === "kpi") {
    const field = viz.y_field || firstNumericField(rows[0]);
    const value = field ? rows[0]?.[field] : Object.values(response.summary || {})[0];
    return <KpiTile label={viz.title || field || "Result"} value={String(value ?? "—")} />;
  }

  if (viz.type === "bar" || viz.type === "line") {
    const xField = viz.x_field || Object.keys(rows[0])[0];
    const yField = viz.y_field || firstNumericField(rows[0]) || Object.keys(rows[0])[1];
    const data = rows.slice(0, 50);
    const ChartComp = viz.type === "bar" ? BarChart : LineChart;
    return (
      <div style={{ width: "100%", height: 260 }}>
        {viz.title && (
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: "var(--text-secondary)" }}>
            {viz.title}
          </div>
        )}
        <ResponsiveContainer width="100%" height="100%">
          <ChartComp data={data} margin={{ top: 8, right: 12, left: 0, bottom: 8 }}>
            <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
            <XAxis
              dataKey={xField}
              tick={{ fill: "var(--chart-muted)", fontSize: 11 }}
              axisLine={{ stroke: "var(--chart-axis)" }}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: "var(--chart-muted)", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              width={44}
            />
            <Tooltip
              contentStyle={{
                background: "var(--surface)",
                border: "1px solid var(--border)",
                borderRadius: 10,
                fontSize: 12,
              }}
            />
            {viz.type === "bar" ? (
              <Bar dataKey={yField} fill="var(--chart-series-1)" radius={[4, 4, 0, 0]} maxBarSize={36} />
            ) : (
              <Line
                type="monotone"
                dataKey={yField}
                stroke="var(--chart-series-1)"
                strokeWidth={2}
                dot={{ r: 3 }}
              />
            )}
          </ChartComp>
        </ResponsiveContainer>
      </div>
    );
  }

  if (viz.type === "pie") {
    const nameField = viz.x_field || Object.keys(rows[0])[0];
    const valueField = viz.y_field || firstNumericField(rows[0]) || Object.keys(rows[0])[1];
    const sorted = [...rows].sort(
      (a, b) => Number(b[valueField] ?? 0) - Number(a[valueField] ?? 0)
    );
    const top = sorted.slice(0, 6);
    const rest = sorted.slice(6);
    const restTotal = rest.reduce((sum, r) => sum + Number(r[valueField] ?? 0), 0);
    const data = top.map((r) => ({ name: String(r[nameField]), value: Number(r[valueField] ?? 0) }));
    if (rest.length > 0) data.push({ name: "Other", value: restTotal });

    return (
      <div style={{ width: "100%", height: 260 }}>
        {viz.title && (
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: "var(--text-secondary)" }}>
            {viz.title}
          </div>
        )}
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={data} dataKey="value" nameKey="name" innerRadius={50} outerRadius={80} paddingAngle={2}>
              {data.map((_, i) => (
                <Cell key={i} fill={i < PIE_COLORS.length ? PIE_COLORS[i] : "var(--chart-muted)"} />
              ))}
            </Pie>
            <Legend wrapperStyle={{ fontSize: 12, color: "var(--text-secondary)" }} />
            <Tooltip
              contentStyle={{
                background: "var(--surface)",
                border: "1px solid var(--border)",
                borderRadius: 10,
                fontSize: 12,
              }}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
    );
  }

  return null;
}

function DataTable({ rows }: { rows: Record<string, unknown>[] }) {
  if (rows.length === 0) return null;
  const columns = Object.keys(rows[0]);
  return (
    <div className="scroll-thin" style={{ overflowX: "auto", maxHeight: 320, overflowY: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr style={{ position: "sticky", top: 0, background: "var(--surface)" }}>
            {columns.map((c) => (
              <th
                key={c}
                style={{
                  textAlign: "left",
                  padding: "6px 12px",
                  color: "var(--text-secondary)",
                  fontSize: 11,
                  borderBottom: "1px solid var(--border)",
                }}
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 100).map((row, i) => (
            <tr key={i} style={{ borderTop: "1px solid var(--border)" }}>
              {columns.map((c) => (
                <td key={c} style={{ padding: "7px 12px", whiteSpace: "nowrap" }}>
                  {row[c] === null || row[c] === undefined ? (
                    <span style={{ color: "var(--text-tertiary)" }}>—</span>
                  ) : (
                    String(row[c])
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Timeline({ events }: { events: QueryResponse["timeline"] }) {
  if (events.length === 0) return null;
  return (
    <div className="stack" style={{ gap: 0, marginTop: 4 }}>
      {events.map((e, i) => (
        <div key={i} className="row" style={{ gap: 12, alignItems: "flex-start" }}>
          <div className="stack" style={{ alignItems: "center", width: 10 }}>
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                background: "var(--accent)",
                marginTop: 5,
                flexShrink: 0,
              }}
            />
            {i < events.length - 1 && <span style={{ width: 1, flex: 1, background: "var(--border)" }} />}
          </div>
          <div style={{ paddingBottom: 14 }}>
            {e.timestamp && (
              <div style={{ fontSize: 11.5, color: "var(--text-tertiary)" }}>{e.timestamp}</div>
            )}
            <div style={{ fontSize: 13.5 }}>{e.event}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

export function ResultView({ response }: { response: QueryResponse }) {
  const hasSummary = response.summary && Object.keys(response.summary).length > 0;

  return (
    <div className="stack" style={{ gap: 16 }}>
      <p style={{ whiteSpace: "pre-wrap", fontSize: 14.5, lineHeight: 1.55 }}>{response.answer}</p>

      {response.entity && (
        <div className="row" style={{ gap: 8 }}>
          <span className="pill pill-accent">
            {response.entity.type} · {response.entity.id}
          </span>
        </div>
      )}

      {response.agents_consulted?.length > 0 && (
        <p style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
          Consulted: {response.agents_consulted.join(", ")}
        </p>
      )}

      {hasSummary && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
            gap: 10,
          }}
        >
          {Object.entries(response.summary!).map(([k, v]) => (
            <div
              key={k}
              style={{
                background: "var(--surface-sunken)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-md)",
                padding: "10px 12px",
              }}
            >
              <div style={{ fontSize: 11, color: "var(--text-secondary)", textTransform: "capitalize" }}>
                {k.replace(/_/g, " ")}
              </div>
              <div style={{ fontSize: 14, fontWeight: 600, marginTop: 2 }}>{String(v)}</div>
            </div>
          ))}
        </div>
      )}

      <Chart response={response} />

      {(response.timeline?.length ?? 0) > 0 && (
        <div>
          <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 8 }}>
            TIMELINE
          </div>
          <Timeline events={response.timeline} />
        </div>
      )}

      {(response.result?.length ?? 0) > 0 && (!response.visualization || response.visualization.type === "table") && (
        <DataTable rows={response.result} />
      )}

      {(response.missing_info?.length ?? 0) > 0 && (
        <p style={{ fontSize: 12.5, color: "var(--text-tertiary)" }}>
          Not available in your data: {response.missing_info.join(", ")}
        </p>
      )}
    </div>
  );
}
