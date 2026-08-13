import { describe, expect, it } from 'vitest'
import { PERIOD_KEYS, resolvePeriod } from './period'

const TODAY = new Date('2026-08-13T00:00:00Z')

describe('resolvePeriod', () => {
  it('기본값은 1년이다', () => {
    expect(resolvePeriod(undefined, TODAY).key).toBe('1Y')
  })

  it('알 수 없는 값도 기본값으로 떨어진다', () => {
    expect(resolvePeriod('nonsense', TODAY).key).toBe('1Y')
  })

  it('ALL은 시작일이 없다', () => {
    expect(resolvePeriod('ALL', TODAY).from).toBeNull()
  })

  it('1M은 한 달 전이다', () => {
    expect(resolvePeriod('1M', TODAY).from?.toISOString().slice(0, 10)).toBe('2026-07-13')
  })

  it('3Y는 3년 전이다', () => {
    expect(resolvePeriod('3Y', TODAY).from?.toISOString().slice(0, 10)).toBe('2023-08-13')
  })

  it('모든 키를 해석할 수 있다', () => {
    for (const key of PERIOD_KEYS) {
      expect(resolvePeriod(key, TODAY).key).toBe(key)
    }
  })
})
