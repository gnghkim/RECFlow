import Decimal from 'decimal.js'

export const DASH = '—'

export function toDecimal(value: string | number | null | undefined): Decimal | null {
  if (value === null || value === undefined) return null
  const text = String(value).trim()
  if (text === '') return null
  try {
    const decimal = new Decimal(text)
    return decimal.isFinite() ? decimal : null
  } catch {
    return null
  }
}

export function formatKrw(
  value: string | number | null | undefined,
  options: { compact?: boolean } = {},
): string {
  const decimal = toDecimal(value)
  if (decimal === null) return DASH

  if (options.compact) {
    const absolute = decimal.abs()
    if (absolute.gte(100_000_000)) {
      return `${trimZeros(decimal.div(100_000_000).toFixed(2))}억원`
    }
    if (absolute.gte(10_000)) {
      return `${group(decimal.div(10_000).toFixed(0))}만원`
    }
  }

  return `${group(decimal.toFixed(0))}원`
}

export function formatQuantity(value: string | number | null | undefined): string {
  const decimal = toDecimal(value)
  if (decimal === null) return DASH
  return group(trimZeros(decimal.toFixed(2)))
}

export function formatPercent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return DASH
  return `${value.toFixed(digits)}%`
}

function group(text: string): string {
  const negative = text.startsWith('-')
  const [integer, fraction] = (negative ? text.slice(1) : text).split('.')
  const grouped = integer.replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  const result = fraction ? `${grouped}.${fraction}` : grouped
  return negative ? `-${result}` : result
}

function trimZeros(text: string): string {
  return text.includes('.') ? text.replace(/\.?0+$/, '') : text
}
