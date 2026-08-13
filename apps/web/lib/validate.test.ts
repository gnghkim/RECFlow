import { describe, expect, it } from 'vitest'
import { DECIMAL_LIMITS, parseDateField, parseDecimalField, parsePositiveInt } from './validate'

describe('parseDecimalField', () => {
  it('숫자 문자열을 통과시킨다', () => {
    expect(parseDecimalField('1000.5', '수량')).toEqual({ ok: true, value: '1000.5' })
  })

  it('숫자 타입도 받는다', () => {
    expect(parseDecimalField(1000, '수량')).toEqual({ ok: true, value: '1000' })
  })

  it('음수를 거부한다', () => {
    const result = parseDecimalField('-1', '수량')
    expect(result.ok).toBe(false)
  })

  it('숫자가 아니면 거부하고 필드명을 알려준다', () => {
    const result = parseDecimalField('abc', '단가')
    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.error).toContain('단가')
  })

  it('빈 값을 거부한다', () => {
    expect(parseDecimalField('', '수량').ok).toBe(false)
    expect(parseDecimalField(null, '수량').ok).toBe(false)
  })

  it('0은 허용한다', () => {
    expect(parseDecimalField('0', '수량').ok).toBe(true)
  })
})

describe('parseDecimalField 자릿수 한계', () => {
  it('컬럼 한계를 넘으면 거부하고 한계를 알려준다', () => {
    // rec_weight 는 Decimal(4,2) 라 99.99 가 최대다. 넘기면 DB가 500으로 터진다.
    const result = parseDecimalField('1000', 'REC 가중치', { max: DECIMAL_LIMITS.weight })
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.error).toContain('REC 가중치')
      expect(result.error).toContain('99.99')
    }
  })

  it('한계값 자체는 허용한다', () => {
    expect(parseDecimalField('99.99', 'REC 가중치', { max: DECIMAL_LIMITS.weight }).ok).toBe(true)
  })

  it('한계를 지정하지 않으면 검사하지 않는다', () => {
    expect(parseDecimalField('999999', '수량').ok).toBe(true)
  })

  it('큰 금액 한계도 동작한다', () => {
    expect(parseDecimalField('1e20', '매각금액', { max: DECIMAL_LIMITS.amount }).ok).toBe(false)
    expect(parseDecimalField('999999999999999', '매각금액', { max: DECIMAL_LIMITS.amount }).ok).toBe(true)
  })

  it('소수 자릿수가 많으면 반올림해서 받는다', () => {
    // Postgres 가 어차피 scale 2 로 반올림한다. 오류로 막을 이유가 없다.
    const result = parseDecimalField('1.005', 'REC 가중치', { max: DECIMAL_LIMITS.weight })
    expect(result.ok).toBe(true)
    if (result.ok) expect(result.value).toBe('1.01')
  })
})

describe('parseDateField', () => {
  it('YYYY-MM-DD를 받는다', () => {
    const result = parseDateField('2026-08-06', '발급일')
    expect(result.ok).toBe(true)
    if (result.ok) expect(result.value.toISOString().slice(0, 10)).toBe('2026-08-06')
  })

  it('형식이 틀리면 거부한다', () => {
    expect(parseDateField('2026/08/06', '발급일').ok).toBe(false)
  })

  it('존재하지 않는 날짜를 거부한다', () => {
    expect(parseDateField('2026-02-30', '발급일').ok).toBe(false)
  })
})

describe('parsePositiveInt', () => {
  it('양의 정수를 받는다', () => {
    expect(parsePositiveInt('12', 'id')).toEqual({ ok: true, value: 12 })
  })

  it('0과 음수를 거부한다', () => {
    expect(parsePositiveInt('0', 'id').ok).toBe(false)
    expect(parsePositiveInt('-1', 'id').ok).toBe(false)
  })

  it('소수를 거부한다', () => {
    expect(parsePositiveInt('1.5', 'id').ok).toBe(false)
  })
})
