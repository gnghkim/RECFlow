export function Badge({ children, tone = 'neutral' }: { children: React.ReactNode; tone?: 'neutral' | 'up' | 'down' }) {
  const styles =
    tone === 'up'
      ? 'bg-[var(--color-up)]/10 text-[var(--color-up)]'
      : tone === 'down'
        ? 'bg-[var(--color-down)]/10 text-[var(--color-down)]'
        : 'bg-[var(--color-muted)]/10 text-[var(--color-muted)]'
  return <span className={`rounded px-2 py-0.5 text-xs font-medium ${styles}`}>{children}</span>
}
