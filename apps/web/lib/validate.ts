import Decimal from 'decimal.js'

export type ParseResult<T> = { ok: true; value: T } | { ok: false; error: string }

export function parseDecimalField(value: unknown, field: string): ParseResult<string> {
  if (value === null || value === undefined || value === '') {
    return { ok: false, error: `${field}을(를) 입력하세요.` }
  }
  try {
    const decimal = new Decimal(String(value).trim())
    if (!decimal.isFinite()) return { ok: false, error: `${field}이(가) 올바른 숫자가 아닙니다.` }
    if (decimal.isNegative()) return { ok: false, error: `${field}은(는) 0 이상이어야 합니다.` }
    return { ok: true, value: decimal.toString() }
  } catch {
    return { ok: false, error: `${field}이(가) 올바른 숫자가 아닙니다.` }
  }
}

export function parseDateField(value: unknown, field: string): ParseResult<Date> {
  const text = String(value ?? '').trim()
  if (!/^\d{4}-\d{2}-\d{2}$/.test(text)) {
    return { ok: false, error: `${field}은(는) YYYY-MM-DD 형식이어야 합니다.` }
  }
  const date = new Date(`${text}T00:00:00.000Z`)
  // Date는 2026-02-30을 3월 2일로 넘겨버린다. 되돌려 비교해 걸러낸다.
  if (Number.isNaN(date.getTime()) || date.toISOString().slice(0, 10) !== text) {
    return { ok: false, error: `${field}이(가) 존재하지 않는 날짜입니다.` }
  }
  return { ok: true, value: date }
}

export function parsePositiveInt(value: unknown, field: string): ParseResult<number> {
  const text = String(value ?? '').trim()
  if (!/^\d+$/.test(text)) return { ok: false, error: `${field}이(가) 올바르지 않습니다.` }
  const parsed = Number(text)
  if (parsed <= 0) return { ok: false, error: `${field}이(가) 올바르지 않습니다.` }
  return { ok: true, value: parsed }
}
