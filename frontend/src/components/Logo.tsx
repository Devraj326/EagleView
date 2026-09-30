export function Logo({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" fill="none" aria-hidden="true">
      <rect width="28" height="28" rx="8" fill="var(--accent)" />
      <rect x="8" y="7" width="3" height="14" rx="1" fill="var(--surface)" />
      <rect x="8" y="7" width="11" height="3" rx="1" fill="var(--surface)" />
      <rect x="8" y="12.5" width="9" height="3" rx="1" fill="var(--surface)" />
      <rect x="8" y="18" width="11" height="3" rx="1" fill="var(--surface)" />
    </svg>
  );
}
