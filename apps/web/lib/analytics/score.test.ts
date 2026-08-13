import { describe, expect, it } from 'vitest'
import { decisionScore } from './score'

function input(overrides: Partial<Parameters<typeof decisionScore>[0]> = {}) {
  return {
    percentile: 50,
    currentPrice: 71000,
    ma8: 70000,
    ma26: 69000,
    recentVolume: 100000,
    averageVolume3m: 100000,
    ...overrides,
  }
}

describe('가격 위치 점수', () => {
  it.each([
    [90, 2],
    [80, 2],
    [70, 1],
    [60, 1],
    [50, 0],
    [40, 0],
    [30, -1],
    [20, -1],
    [10, -2],
  ])('백분위 %s -> %s점', (value, expected) => {
    expect(decisionScore(input({ percentile: value })).breakdown.position).toBe(expected)
  })
})

describe('추세 점수', () => {
  it('현재가 > MA8 > MA26 이면 +2', () => {
    const result = decisionScore(input({ currentPrice: 72000, ma8: 71000, ma26: 70000 }))
    expect(result.breakdown.trend).toBe(2)
  })

  it('현재가가 MA26 위지만 정배열이 아니면 +1', () => {
    const result = decisionScore(input({ currentPrice: 72000, ma8: 73000, ma26: 70000 }))
    expect(result.breakdown.trend).toBe(1)
  })

  it('현재가 < MA8 < MA26 이면 -2', () => {
    const result = decisionScore(input({ currentPrice: 68000, ma8: 69000, ma26: 70000 }))
    expect(result.breakdown.trend).toBe(-2)
  })

  it('현재가가 MA26 아래면 -1', () => {
    const result = decisionScore(input({ currentPrice: 68000, ma8: 67000, ma26: 70000 }))
    expect(result.breakdown.trend).toBe(-1)
  })

  it('현재가가 MA26과 같으면 0', () => {
    const result = decisionScore(input({ currentPrice: 70000, ma8: 71000, ma26: 70000 }))
    expect(result.breakdown.trend).toBe(0)
  })
})

describe('거래량 점수', () => {
  it('3개월 평균의 1.2배를 넘으면 +1', () => {
    expect(decisionScore(input({ recentVolume: 121, averageVolume3m: 100 })).breakdown.volume).toBe(1)
  })

  it('평균 수준이면 0', () => {
    expect(decisionScore(input({ recentVolume: 100, averageVolume3m: 100 })).breakdown.volume).toBe(0)
  })

  it('평균의 0.7배 미만이면 -1', () => {
    expect(decisionScore(input({ recentVolume: 60, averageVolume3m: 100 })).breakdown.volume).toBe(-1)
  })

  it('평균 거래량이 0이면 null이다', () => {
    expect(decisionScore(input({ averageVolume3m: 0 })).breakdown.volume).toBeNull()
  })
})

describe('데이터 부족 처리', () => {
  it('구성요소가 하나라도 없으면 총점은 null이다', () => {
    const result = decisionScore(input({ percentile: null }))
    expect(result.total).toBeNull()
    expect(result.complete).toBe(false)
    expect(result.label).toBe('데이터 부족')
  })

  it('계산 가능한 구성요소는 그대로 보여준다', () => {
    // 총점을 못 내도 아는 것까지는 보여준다.
    const result = decisionScore(input({ percentile: null }))
    expect(result.breakdown.trend).not.toBeNull()
    expect(result.breakdown.volume).not.toBeNull()
  })

  it('MA26이 없으면 추세는 null이다', () => {
    expect(decisionScore(input({ ma26: null })).breakdown.trend).toBeNull()
  })
})

describe('종합 판정', () => {
  it('최고 조합은 +5점 적극 매도 검토', () => {
    const result = decisionScore(input({
      percentile: 90, currentPrice: 72000, ma8: 71000, ma26: 70000,
      recentVolume: 200, averageVolume3m: 100,
    }))
    expect(result.total).toBe(5)
    expect(result.label).toBe('적극 매도 검토')
    expect(result.complete).toBe(true)
  })

  it('+2점이면 일부 매도 검토', () => {
    // 위치 +1, 추세 +1, 거래량 0
    const result = decisionScore(input({
      percentile: 70, currentPrice: 72000, ma8: 73000, ma26: 70000,
      recentVolume: 100, averageVolume3m: 100,
    }))
    expect(result.total).toBe(2)
    expect(result.label).toBe('일부 매도 검토')
  })

  it('0점이면 관망', () => {
    // 위치 0, 추세 0, 거래량 0
    const result = decisionScore(input({
      percentile: 50, currentPrice: 70000, ma8: 71000, ma26: 70000,
      recentVolume: 100, averageVolume3m: 100,
    }))
    expect(result.total).toBe(0)
    expect(result.label).toBe('관망')
  })

  it('-2점이면 매도 신중', () => {
    // 위치 -1, 추세 -1, 거래량 0
    const result = decisionScore(input({
      percentile: 30, currentPrice: 68000, ma8: 67000, ma26: 70000,
      recentVolume: 100, averageVolume3m: 100,
    }))
    expect(result.total).toBe(-2)
    expect(result.label).toBe('매도 신중')
  })

  it('최저 조합은 -5점 매도 신중', () => {
    const result = decisionScore(input({
      percentile: 5, currentPrice: 68000, ma8: 69000, ma26: 70000,
      recentVolume: 10, averageVolume3m: 100,
    }))
    expect(result.total).toBe(-5)
    expect(result.label).toBe('매도 신중')
  })
})
