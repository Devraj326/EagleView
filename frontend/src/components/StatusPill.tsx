const STATUS_STYLES: Record<string, { label: string; className: string }> = {
  UPLOADED: { label: "Uploaded", className: "pill-neutral" },
  ANALYZING: { label: "Analyzing", className: "pill-accent" },
  SCHEMA_PROPOSED: { label: "Needs review", className: "pill-warning" },
  LOADING: { label: "Loading", className: "pill-accent" },
  READY: { label: "Ready", className: "pill-success" },
  FAILED: { label: "Failed", className: "pill-danger" },
};

export function StatusPill({ status }: { status: string }) {
  const style = STATUS_STYLES[status] || { label: status, className: "pill-neutral" };
  return <span className={`pill ${style.className}`}>{style.label}</span>;
}
