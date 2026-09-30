export function Spinner({ size = 18, color }: { size?: number; color?: string }) {
  return (
    <span
      style={{
        display: "inline-block",
        width: size,
        height: size,
        borderRadius: "50%",
        border: `2.5px solid ${color || "var(--border-strong)"}`,
        borderTopColor: color || "var(--accent)",
        animation: "spin 0.7s linear infinite",
      }}
    />
  );
}
