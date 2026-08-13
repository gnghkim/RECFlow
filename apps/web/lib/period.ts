export const PERIOD_KEYS = ['1M', '3M', '6M', '1Y', '3Y', 'ALL'] as const
export type PeriodKey = (typeof PERIOD_KEYS)[number]

export const DEFAULT_PERIOD: PeriodKey = '1Y'

const MONTHS: Record<Exclude<PeriodKey, 'ALL'>, number> = {
  '1M': 1,
  '3M': 3,
  '6M': 6,
  '1Y': 12,
  '3Y': 36,
}

export const PERIOD_LABELS: Record<PeriodKey, string> = {
  '1M': '1개월',
  '3M': '3개월',
  '6M': '6개월',
  '1Y': '1년',
  '3Y': '3년',
  ALL: '전체',
}

export function resolvePeriod(
  key: string | undefined,
  today: Date = new Date(),
): { key: PeriodKey; from: Date | null } {
  const resolved = (PERIOD_KEYS as readonly string[]).includes(key ?? '')
    ? (key as PeriodKey)
    : DEFAULT_PERIOD

  if (resolved === 'ALL') return { key: resolved, from: null }

  const from = new Date(today)
  from.setUTCMonth(from.getUTCMonth() - MONTHS[resolved])
  return { key: resolved, from }
}
