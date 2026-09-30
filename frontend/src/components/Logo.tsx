export function Logo({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" fill="none" aria-hidden="true">
      <rect width="28" height="28" rx="8" fill="var(--accent)" />
      <path
        d="M9 7.5h5c3.6 0 6.1 2.6 6.1 6s-2.5 6-6.1 6H9v-12Zm2.8 2.5v7h2.1c2.1 0 3.4-1.4 3.4-3.5s-1.3-3.5-3.4-3.5h-2.1Z"
        fill="var(--surface)"
      />
    </svg>
  );
}
