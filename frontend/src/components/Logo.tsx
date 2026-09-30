export function Logo({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" fill="none" aria-hidden="true">
      <rect width="28" height="28" rx="7" fill="var(--accent)" />
      <path
        d="M8 7h12v3H11v3h7v3h-7v3h9v3H8V7Z"
        fill="white"
      />
    </svg>
  );
}
