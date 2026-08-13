import { describe, expect, it } from 'vitest'
import { MIN_PERCENTILE_SAMPLES, percentile, priceBand } from './percentile'

function series(length: number, start = 1): number[] {
  return Array.from({ length }, (_, index) => start + index)
}

describe('percentile', () => {
  it('표본이 최소 개수 미만이면 null', () => {
    expect(percentile(50, series(MIN_PERCENTILE_SAMPLES - 1))).toBeNull()
  })

  it('최소 개수를 채우면 값을 낸다', () => {
    expect(percentile(50, series(MIN_PERCENTILE_SAMPLES))).not.toBeNull()
  })

  it('최댓값은 100', () => {
    const window = series(30)
    expect(percentile(30, window)).toBe(100)
  })

  it('최솟값은 이하 개수 1건이므로 100/30', () => {
    const window = series(30)
    expect(percentile(1, window)).toBeCloseTo((1 / 30) * 100, 6)
  })

  it('동점은 이하에 산입한다', () => {
    const window = [10, 10, 10, ...series(27, 100)]
    expect(percentile(10, window)).toBeCloseTo((3 / 30) * 100, 6)
  })

  it('창의 최댓값보다 크면 100', () => {
    expect(percentile(999, series(30))).toBe(100)
  })

  it('창의 최솟값보다 작으면 0', () => {
    expect(percentile(-1, series(30))).toBe(0)
  })

  it('빈 창은 null', () => {
    expect(percentile(50, [])).toBeNull()
  })
})

describe('priceBand', () => {
  it('null이면 null', () => {
    expect(priceBand(null)).toBeNull()
  })

  it.each([
    [0, '매우 낮음'],
    [19.9, '매우 낮음'],
    [20, '낮음'],
    [39.9, '낮음'],
    [40, '보통'],
    [59.9, '보통'],
    [60, '높음'],
    [79.9, '높음'],
    [80, '매우 높음'],
    [100, '매우 높음'],
  ])('%s%% -> %s', (value, label) => {
    expect(priceBand(value)?.label).toBe(label)
  })
})
