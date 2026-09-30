import { Check, UploadCloud, Database, ArrowRight } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AgentLogPanel } from "../components/AgentLogPanel";
import { NavBar } from "../components/NavBar";
import { SchemaMappingTable } from "../components/SchemaMappingTable";
import { Spinner } from "../components/Spinner";
import { ApiError, api } from "../lib/api";
import type { DatasetSummary, DemoSeedResult, DomainColumn, DomainResult, ReadyDomain } from "../lib/types";

type Phase = "idle" | "uploading" | "analyzing" | "review" | "confirming" | "success" | "error";

const STEPS: { key: Phase; label: string }[] = [
  { key: "idle", label: "Upload" },
  { key: "analyzing", label: "Analyze" },
  { key: "review", label: "Review mapping" },
  { key: "confirming", label: "Confirm" },
  { key: "success", label: "Ready" },
];

function stepIndex(phase: Phase): number {
  if (phase === "uploading") return 0;
  return Math.max(0, STEPS.findIndex((s) => s.key === phase));
}

export function OnboardingPage() {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [readyDomains, setReadyDomains] = useState<ReadyDomain[]>([]);
  const [datasetHistory, setDatasetHistory] = useState<DatasetSummary[]>([]);
  const [phase, setPhase] = useState<Phase>("idle");
  const [activeDatasetId, setActiveDatasetId] = useState<string | null>(null);
  const [domains, setDomains] = useState<DomainResult[]>([]);
  const [editedColumns, setEditedColumns] = useState<Record<string, DomainColumn[]>>({});
  const [activeTab, setActiveTab] = useState(0);
  const [errorMsg, setErrorMsg] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [seedingDemo, setSeedingDemo] = useState(false);
  const [seedResults, setSeedResults] = useState<DemoSeedResult[] | null>(null);
  const [agentLog, setAgentLog] = useState<string[]>([]);

  const appendLog = useCallback((entries: string[]) => {
    if (entries.length) setAgentLog((prev) => [...prev, ...entries]);
  }, []);

  const refreshDatasets = useCallback(() => {
    api
      .listDatasets()
      .then((r) => {
        setDatasetHistory(r.datasets);
        setReadyDomains(r.domains);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    refreshDatasets();
  }, [refreshDatasets]);

  const processingData = datasetHistory.some((d) => d.status === "ANALYZING" || d.status === "LOADING");
  useEffect(() => {
    if (!seedingDemo && !processingData) return;
    const timer = window.setInterval(refreshDatasets, 10000);
    return () => window.clearInterval(timer);
  }, [seedingDemo, processingData, refreshDatasets]);

  async function runAnalysis(datasetId: string) {
    setPhase("analyzing");
    setErrorMsg("");
    try {
      const result = await api.analyzeDataset(datasetId);
      appendLog(result.agent_log);
      setDomains(result.domains);
      setEditedColumns(Object.fromEntries(result.domains.map((d) => [d.domain_id, d.columns])));
      setActiveTab(0);
      setPhase("review");
    } catch (e) {
      setErrorMsg(e instanceof ApiError ? e.message : "Analysis failed");
      setPhase("error");
    } finally {
      refreshDatasets();
    }
  }

  async function handleFile(file: File) {
    setPhase("uploading");
    setErrorMsg("");
    try {
      const dataset = await api.uploadDataset(file);
      setActiveDatasetId(dataset.id);
      await runAnalysis(dataset.id);
    } catch (e) {
      setErrorMsg(e instanceof ApiError ? e.message : "Upload failed");
      setPhase("error");
    }
  }

  async function runSeedDemo() {
    setSeedingDemo(true);
    setSeedResults(null);
    try {
      const { results, agent_log } = await api.seedDemo();
      appendLog(agent_log);
      setSeedResults(results);
    } catch (e) {
      setSeedResults([
        {
          name: "Demo seed",
          status: "FAILED",
          error: e instanceof ApiError ? e.message : "Failed to seed demo data",
        },
      ]);
    } finally {
      setSeedingDemo(false);
      refreshDatasets();
    }
  }

  function resumeDataset(dataset: DatasetSummary) {
    setActiveDatasetId(dataset.id);
    setErrorMsg("");
    if (dataset.status === "READY") {
      setPhase("success");
    } else if (dataset.status === "FAILED") {
      setErrorMsg(dataset.error_message || "This dataset failed to process.");
      setPhase("error");
    } else {
      // Re-run analysis rather than trying to reconstruct the in-progress
      // review state from scratch — simplest correct option for a dataset
      // that was never confirmed.
      runAnalysis(dataset.id);
    }
  }

  async function handleConfirm() {
    if (!activeDatasetId) return;
    setPhase("confirming");
    setErrorMsg("");
    try {
      const body = {
        domains: domains.map((d) => ({
          domain_id: d.domain_id,
          columns: (editedColumns[d.domain_id] || d.columns).map((c) => ({
            id: c.id,
            target_column: c.target_column,
            target_type: c.target_type,
            nullable: c.nullable,
            include: c.include,
          })),
        })),
      };
      const result = await api.confirmDataset(activeDatasetId, body);
      appendLog(result.agent_log);
      setPhase("success");
      refreshDatasets();
    } catch (e) {
      setErrorMsg(e instanceof ApiError ? e.message : "Failed to merge domain tables");
      setPhase("error");
    }
  }

  function startOver() {
    setPhase("idle");
    setActiveDatasetId(null);
    setDomains([]);
    setEditedColumns({});
    setErrorMsg("");
  }

  const inProgress = datasetHistory.filter((d) => d.status !== "READY" && d.status !== "FAILED");
  const ready = datasetHistory.filter((d) => d.status === "READY");
  const failed = datasetHistory.filter((d) => d.status === "FAILED");

  return (
    <div style={{ minHeight: "100vh" }}>
      <NavBar />
      <div className="container" style={{ paddingTop: 32, paddingBottom: 64 }}>
        <div className="page-heading">
          <div>
            <h1>Your data</h1>
            <p>Upload a file and review its structure before adding it to your workspace.</p>
          </div>
          <button className="btn btn-secondary" onClick={() => navigate("/dashboard")}>Open analysis <ArrowRight size={15} /></button>
        </div>
        <div className="workspace-content">
        {phase !== "idle" && <Stepper phase={phase} />}

        <div style={{ marginTop: 28 }}>
          {(phase === "idle" || phase === "uploading") && (
            <Dropzone
              dragOver={dragOver}
              setDragOver={setDragOver}
              uploading={phase === "uploading"}
              onFile={handleFile}
              fileInputRef={fileInputRef}
            />
          )}

          {phase === "idle" && (
            <DemoSeedCard seeding={seedingDemo || processingData} results={seedResults} onSeed={runSeedDemo} />
          )}

          {phase === "analyzing" && (
            <div className="card fade-in-up" style={{ padding: 48, textAlign: "center" }}>
              <Spinner size={30} />
              <p style={{ marginTop: 16, fontWeight: 560 }}>
                Analyzing your file…
              </p>
              <p style={{ color: "var(--text-secondary)", fontSize: 13, marginTop: 4 }}>
                Identifying the data and preparing column mappings for your review.
              </p>
            </div>
          )}

          {phase === "review" && domains.length > 0 && (
            <ReviewStep
              domains={domains}
              activeTab={activeTab}
              setActiveTab={setActiveTab}
              editedColumns={editedColumns}
              setEditedColumns={setEditedColumns}
              onConfirm={handleConfirm}
              onCancel={startOver}
            />
          )}

          {phase === "confirming" && (
            <div className="card fade-in-up" style={{ padding: 48, textAlign: "center" }}>
              <Spinner size={30} />
              <p style={{ marginTop: 16, fontWeight: 560 }}>Adding your data…</p>
              <p style={{ color: "var(--text-secondary)", fontSize: 13, marginTop: 4 }}>
                Each confirmed domain's table is created or extended, then loaded.
              </p>
            </div>
          )}

          {phase === "success" && (
            <div className="card fade-in-up" style={{ padding: 40, textAlign: "center" }}>
              <div
                className="row"
                style={{
                  width: 52,
                  height: 52,
                  borderRadius: "50%",
                  background: "var(--success-soft)",
                  color: "var(--success)",
                  justifyContent: "center",
                  margin: "0 auto 16px",
                }}
              >
                <Check size={24} strokeWidth={2.5} />
              </div>
              <h2 style={{ fontSize: 20, fontWeight: 620 }}>Data is ready</h2>
              <p style={{ color: "var(--text-secondary)", marginTop: 6, fontSize: 14 }}>
                Your data has been merged into Snowflake. You can ask questions about it now.
              </p>
              <div className="row" style={{ justifyContent: "center", gap: 10, marginTop: 22 }}>
                <button className="btn btn-secondary" onClick={startOver}>
                  Upload another
                </button>
                <button className="btn btn-primary" onClick={() => navigate("/dashboard")}>
                  Open dashboard
                </button>
              </div>
            </div>
          )}

          {phase === "error" && (
            <div className="card fade-in-up" style={{ padding: 32 }}>
              <p className="pill pill-danger" style={{ marginBottom: 12 }}>
                Something went wrong
              </p>
              <p style={{ fontSize: 14, color: "var(--text)" }}>{errorMsg}</p>
              <div className="row" style={{ gap: 10, marginTop: 18 }}>
                <button className="btn btn-secondary" onClick={startOver}>
                  Start over
                </button>
                {activeDatasetId && (
                  <button className="btn btn-primary" onClick={() => runAnalysis(activeDatasetId)}>
                    Retry analysis
                  </button>
                )}
              </div>
            </div>
          )}
        </div>

        {(inProgress.length > 0 || ready.length > 0 || failed.length > 0) && (
          <div style={{ marginTop: 48 }}>
            {inProgress.length > 0 && (
              <DatasetList title="In progress" datasets={inProgress} onSelect={resumeDataset} disabled={seedingDemo || processingData} />
            )}
            {ready.length > 0 && <DatasetList title="Ready to use" datasets={ready} onSelect={resumeDataset} />}
            {failed.length > 0 && <DatasetList title="Needs attention" datasets={failed} onSelect={resumeDataset} />}
          </div>
        )}

        {readyDomains.length > 0 && (
          <div style={{ marginTop: 28 }}>
            <h2 style={{ fontSize: 13, color: "var(--text-secondary)", fontWeight: 600, marginBottom: 10 }}>
              DATA TABLES
            </h2>
            <div className="stack" style={{ gap: 8 }}>
              {readyDomains.map((d) => (
                <div
                  key={d.agent_key}
                  className="card row"
                  style={{ padding: "12px 18px", justifyContent: "space-between" }}
                >
                  <span style={{ fontWeight: 560, fontSize: 14 }}>{d.agent_label}</span>
                  <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                    {d.table_name} · {d.row_count.toLocaleString()} rows
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        <AgentLogPanel log={agentLog} onClear={() => setAgentLog([])} />
        </div>
      </div>
    </div>
  );
}

function Stepper({ phase }: { phase: Phase }) {
  const idx = stepIndex(phase);
  return (
    <div className="row pipeline-stepper">
      {STEPS.map((step, i) => (
        <div key={step.key} className="row pipeline-step">
          <div className="row" style={{ gap: 8 }}>
            <span
              className="row"
              style={{
                width: 22,
                height: 22,
                borderRadius: "50%",
                justifyContent: "center",
                fontSize: 11,
                fontWeight: 700,
                background: i <= idx ? "var(--accent)" : "var(--surface-sunken)",
                color: i <= idx ? "white" : "var(--text-tertiary)",
                border: i <= idx ? "none" : "1px solid var(--border)",
                transition: "background 0.2s var(--ease)",
              }}
            >
              {i < idx ? <Check size={12} strokeWidth={3} /> : i + 1}
            </span>
            <span
              style={{
                fontSize: 13,
                fontWeight: i === idx ? 600 : 500,
                color: i <= idx ? "var(--text)" : "var(--text-tertiary)",
                whiteSpace: "nowrap",
              }}
            >
              {step.label}
            </span>
          </div>
          {i < STEPS.length - 1 && (
            <div
              style={{
                flex: 1,
                height: 1,
                background: i < idx ? "var(--accent)" : "var(--border)",
                margin: "0 12px",
                transition: "background 0.2s var(--ease)",
              }}
            />
          )}
        </div>
      ))}
    </div>
  );
}

function Dropzone({
  dragOver,
  setDragOver,
  uploading,
  onFile,
  fileInputRef,
}: {
  dragOver: boolean;
  setDragOver: (v: boolean) => void;
  uploading: boolean;
  onFile: (file: File) => void;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
}) {
  return (
    <div
      className="card upload-dropzone"
      role="button"
      tabIndex={uploading ? -1 : 0}
      aria-label="Upload a CSV, Excel or JSON file"
      aria-disabled={uploading}
      onKeyDown={(e) => { if (!uploading && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); fileInputRef.current?.click(); } }}
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        const file = e.dataTransfer.files?.[0];
        if (file && !uploading) onFile(file);
      }}
      onClick={() => !uploading && fileInputRef.current?.click()}
      style={{
        textAlign: "center",
        cursor: uploading ? "default" : "pointer",
        borderStyle: "dashed",
        borderWidth: 1,
        borderColor: dragOver ? "var(--accent)" : "var(--border-strong)",
        background: dragOver ? "var(--accent-soft)" : "var(--surface)",
        transition: "border-color 0.15s var(--ease), background 0.15s var(--ease)",
      }}
    >
      <input
        ref={fileInputRef}
        type="file"
        accept=".csv,.xlsx,.xls,.json"
        style={{ display: "none" }}
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file && !uploading) onFile(file);
          e.target.value = "";
        }}
      />
      {uploading ? (
        <>
          <Spinner size={30} />
          <p style={{ marginTop: 16, fontWeight: 560 }}>Uploading…</p>
        </>
      ) : (
        <>
          <UploadCloud size={32} strokeWidth={1.5} color="var(--text-tertiary)" />
          <p style={{ marginTop: 12, fontWeight: 600, fontSize: 15 }}>
            Drop your file here
          </p>
          <p style={{ color: "var(--text-secondary)", fontSize: 13, marginTop: 4 }}>
            or select a file from your computer
          </p>
          <div className="file-types"><span>CSV</span><span>XLSX / XLS</span><span>JSON</span></div>
        </>
      )}
    </div>
  );
}

function DemoSeedCard({
  seeding,
  results,
  onSeed,
}: {
  seeding: boolean;
  results: DemoSeedResult[] | null;
  onSeed: () => void;
}) {
  const allReady = results !== null && results.length > 0 && results.every((r) => r.status === "READY");

  return (
    <div className="sample-data">
      <div className="row" style={{ justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div>
          <div className="row" style={{ gap: 8 }}>
            <Database size={17} color="var(--accent)" />
            <strong style={{ fontSize: 14.5 }}>Sample data</strong>
          </div>
          <p style={{ color: "var(--text-secondary)", fontSize: 13, marginTop: 4, maxWidth: 480 }}>
            Customers, products, orders, payments and deliveries. Added automatically without manual review.
          </p>
        </div>
        <button className="btn btn-secondary" onClick={onSeed} disabled={seeding}>
          {seeding ? (
            <>
              <Spinner size={14} /> Loading samples…
            </>
          ) : (
            "Load demo datasets"
          )}
        </button>
      </div>

      {seeding && <p role="status" style={{ color: "var(--text-secondary)", fontSize: 12, marginTop: 14 }}>Preparing your data. This can take several minutes; progress updates below.</p>}
      {results && (
        <div className="stack" style={{ gap: 6, marginTop: 16 }}>
          {results.map((r) => (
            <div key={r.name} className="row" style={{ justifyContent: "space-between", fontSize: 13 }}>
              <span>{r.name}</span>
              <div className="row" style={{ gap: 8 }}>
                {r.error && <span style={{ color: "var(--danger)", fontSize: 12 }}>{r.error}</span>}
                <span className={`pill ${r.status === "READY" ? "pill-success" : "pill-danger"}`}>
                  {r.status}
                </span>
              </div>
            </div>
          ))}
          {allReady && (
            <p style={{ fontSize: 12.5, color: "var(--success)", marginTop: 4 }}>
              All datasets are ready. Head to the dashboard and ask a question.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function ReviewStep({
  domains,
  activeTab,
  setActiveTab,
  editedColumns,
  setEditedColumns,
  onConfirm,
  onCancel,
}: {
  domains: DomainResult[];
  activeTab: number;
  setActiveTab: (i: number) => void;
  editedColumns: Record<string, DomainColumn[]>;
  setEditedColumns: (v: Record<string, DomainColumn[]>) => void;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const current = domains[activeTab];
  const currentColumns = editedColumns[current.domain_id] || current.columns;
  const includedCount = currentColumns.filter((c) => c.include).length;

  return (
    <div className="card fade-in-up" style={{ padding: 28 }}>
      <p style={{ color: "var(--text-secondary)", fontSize: 13, marginBottom: 16 }}>
        The Orchestrator Agent routed this file to <strong>{domains.length}</strong> domain agent(s):
      </p>

      <div className="row" style={{ gap: 6, borderBottom: "1px solid var(--border)", marginBottom: 20 }}>
        {domains.map((d, i) => (
          <button
            key={d.domain_id}
            onClick={() => setActiveTab(i)}
            className="btn btn-ghost"
            style={{
              borderRadius: 0,
              borderBottom: i === activeTab ? "2px solid var(--accent)" : "2px solid transparent",
              color: i === activeTab ? "var(--text)" : "var(--text-secondary)",
              fontWeight: i === activeTab ? 600 : 500,
            }}
          >
            {d.agent_label}
          </button>
        ))}
      </div>

      <div className="row" style={{ justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div>
          <div className="row" style={{ gap: 8 }}>
            <h2 style={{ fontSize: 18, fontWeight: 620 }}>{current.agent_label}</h2>
            <span className="pill pill-neutral">
              {current.is_new_table ? "will create new table" : "will extend existing table"}
            </span>
          </div>
          <p style={{ color: "var(--text-secondary)", fontSize: 13, marginTop: 4 }}>
            Table: <code style={{ fontFamily: "var(--font-mono)" }}>{current.table_name}</code>
          </p>
        </div>
      </div>

      {current.agent_note && (
        <div
          className="row"
          style={{ gap: 8, marginTop: 14, padding: "10px 14px", background: "var(--accent-soft)", borderRadius: 10 }}
        >
          <span style={{ fontSize: 13 }}>🤖 {current.agent_note}</span>
        </div>
      )}

      {(current.data_quality_issues.length > 0 || current.ambiguous_fields.length > 0) && (
        <div className="stack" style={{ gap: 8, marginTop: 18 }}>
          {current.data_quality_issues.map((issue, i) => (
            <div key={i} className="row" style={{ gap: 8, fontSize: 13 }}>
              <span className="pill pill-warning">Data quality</span>
              <span style={{ color: "var(--text-secondary)" }}>{issue}</span>
            </div>
          ))}
          {current.ambiguous_fields.map((field, i) => (
            <div key={i} className="row" style={{ gap: 8, fontSize: 13 }}>
              <span className="pill pill-neutral">Ambiguous</span>
              <span style={{ color: "var(--text-secondary)" }}>{field}</span>
            </div>
          ))}
        </div>
      )}

      <hr className="divider" style={{ margin: "20px 0" }} />

      <SchemaMappingTable
        columns={currentColumns}
        onChange={(cols) => setEditedColumns({ ...editedColumns, [current.domain_id]: cols })}
      />

      <div className="row" style={{ justifyContent: "space-between", marginTop: 24 }}>
        <span style={{ fontSize: 13, color: "var(--text-secondary)" }}>
          {includedCount} of {currentColumns.length} columns will be loaded for this domain
        </span>
        <div className="row" style={{ gap: 10 }}>
          <button className="btn btn-secondary" onClick={onCancel}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={onConfirm}>
            Confirm &amp; merge all domains
          </button>
        </div>
      </div>
    </div>
  );
}

function DatasetList({
  title,
  datasets,
  onSelect,
  disabled = false,
}: {
  title: string;
  datasets: DatasetSummary[];
  onSelect: (d: DatasetSummary) => void;
  disabled?: boolean;
}) {
  return (
    <div style={{ marginBottom: 28 }}>
      <h2 style={{ fontSize: 13, color: "var(--text-secondary)", fontWeight: 600, marginBottom: 10 }}>
        {title.toUpperCase()}
      </h2>
      <div className="stack" style={{ gap: 8 }}>
        {datasets.map((d) => (
          <button
            key={d.id}
            type="button"
            className="card card--interactive row dataset-list-item"
            disabled={disabled}
            style={{ padding: "14px 18px", justifyContent: "space-between" }}
            onClick={() => onSelect(d)}
          >
            <span style={{ fontWeight: 500, fontSize: 14 }}>{d.name}<span style={{ display: "block", color: "var(--text-secondary)", fontSize: 12 }}>{d.row_count.toLocaleString()} {d.status === "READY" ? "rows loaded across tables" : "source rows"}</span></span>
            <span className={`pill ${d.status === "READY" ? "pill-success" : d.status === "FAILED" ? "pill-danger" : "pill-accent"}`}>
              {d.status}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
