import Link from 'next/link'
import { PERIOD_KEYS, PERIOD_LABELS, type PeriodKey } from '@/lib/period'

export function PeriodTabs({ current, basePath }: { current: PeriodKey; basePath: string }) {
  return (
    <div className="flex flex-wrap gap-1">
      {PERIOD_KEYS.map((key) => (
        <Link
          key={key}
          href={`${basePath}?period=${key}`}
          className={`rounded-md px-3 py-1.5 text-sm ${
            key === current
              ? 'bg-[var(--color-accent)] text-white'
              : 'border border-[var(--color-line)] text-[var(--color-muted)] hover:text-[var(--color-ink)]'
          }`}
        >
          {PERIOD_LABELS[key]}
        </Link>
      ))}
    </div>
  )
}
