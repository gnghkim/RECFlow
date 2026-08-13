import Decimal from 'decimal.js'

export type ParseResult<T> = { ok: true; value: T } | { ok: false; error: string }

/**
 * DB 컬럼이 담을 수 있는 최댓값. Prisma 스키마의 Decimal(precision, scale)과 짝을 이룬다.
 *
 * 한계를 넘겨 저장하면 PostgreSQL이 `numeric field overflow`를 내고 화면에는 500만 뜬다.
 * 사용자는 무엇이 잘못됐는지 알 수 없다. 여기서 미리 걸러 400과 함께 한계를 알려준다.
 *
 * 스키마의 precision을 바꾸면 이 값도 함께 고쳐야 한다.
 */
export const DECIMAL_LIMITS = {
  /** plants.rec_weight — Decimal(4,2). 태양광 가중치는 보통 0.7~1.5다. */
  weight: '99.99',
  /** plants.capacity_kw, rec_sales.unit_price, price_targets.target_price — Decimal(12,2) */
  price: '9999999999.99',
  /** rec_inventory.rec_quantity, rec_sales.quantity — Decimal(14,2) */
  quantity: '999999999999.99',
  /** rec_sales.sale_amount — Decimal(18,2) */
  amount: '9999999999999999.99',
} as const

export function parseDecimalField(
  value: unknown,
  field: string,
  options: { max?: string } = {},
): ParseResult<string> {
  if (value === null || value === undefined || value === '') {
    return { ok: false, error: `${field}을(를) 입력하세요.` }
  }
  try {
    const decimal = new Decimal(String(value).trim())
    if (!decimal.isFinite()) return { ok: false, error: `${field}이(가) 올바른 숫자가 아닙니다.` }
    if (decimal.isNegative()) return { ok: false, error: `${field}은(는) 0 이상이어야 합니다.` }

    // DB가 scale 2로 반올림하므로 여기서 미리 맞춘다. 반올림 후 값으로 한계를 본다.
    const rounded = decimal.toDecimalPlaces(2)

    if (options.max !== undefined && rounded.greaterThan(new Decimal(options.max))) {
      return { ok: false, error: `${field}은(는) ${options.max} 이하여야 합니다.` }
    }

    return { ok: true, value: rounded.toString() }
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
