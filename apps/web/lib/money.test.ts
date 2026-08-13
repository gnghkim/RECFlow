import { describe, expect, it } from 'vitest'
import { DASH, formatKrw, formatQuantity, toDecimal } from './money'

describe('toDecimal', () => {
  it('문자열을 변환한다', () => {
    expect(toDecimal('71500.25')?.toString()).toBe('71500.25')
  })

  it('null과 undefined는 null', () => {
    expect(toDecimal(null)).toBeNull()
    expect(toDecimal(undefined)).toBeNull()
  })

  it('빈 문자열은 null', () => {
    expect(toDecimal('')).toBeNull()
  })

  it('숫자가 아니면 null', () => {
    expect(toDecimal('abc')).toBeNull()
  })
})

describe('formatKrw', () => {
  it('천 단위 구분자를 넣는다', () => {
    expect(formatKrw('715000000')).toBe('715,000,000원')
  })

  it('null은 대시', () => {
    expect(formatKrw(null)).toBe(DASH)
  })

  it('소수점은 버린다', () => {
    expect(formatKrw('71500.7')).toBe('71,501원')
  })

  it('compact는 억 단위로 줄인다', () => {
    expect(formatKrw('715000000', { compact: true })).toBe('7.15억원')
  })

  it('compact는 1억 미만이면 만 단위', () => {
    expect(formatKrw('12340000', { compact: true })).toBe('1,234만원')
  })
})

describe('formatQuantity', () => {
  it('정수는 소수점을 붙이지 않는다', () => {
    expect(formatQuantity('10000')).toBe('10,000')
  })

  it('소수가 있으면 두 자리까지 보인다', () => {
    expect(formatQuantity('10000.50')).toBe('10,000.5')
  })

  it('null은 대시', () => {
    expect(formatQuantity(null)).toBe(DASH)
  })
})
