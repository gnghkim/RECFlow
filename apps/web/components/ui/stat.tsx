import { DASH } from '@/lib/money'

export function Stat({
  label,
  value,
  sub,
  tone = 'neutral',
}: {
  label: string
  value: string
  sub?: string | null
  tone?: 'neutral' | 'up' | 'down'
}) {
  const toneClass =
    tone === 'up'
      ? 'text-[var(--color-up)]'
      : tone === 'down'
        ? 'text-[var(--color-down)]'
        : ''

  return (
    <div>
      <p className="text-sm text-[var(--color-muted)]">{label}</p>
      <p className={`tabular mt-1 text-2xl font-semibold tracking-tight ${toneClass}`}>{value}</p>
      {sub ? <p className="tabular mt-0.5 text-sm text-[var(--color-muted)]">{sub}</p> : null}
      {value === DASH ? (
        <p className="mt-0.5 text-xs text-[var(--color-muted)]">데이터 부족</p>
      ) : null}
    </div>
  )
}
