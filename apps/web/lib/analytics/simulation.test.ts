import { describe, expect, it } from 'vitest'
import { simulate, simulateTranches } from './simulation'

describe('simulate', () => {
  it('가격별 예상 매출을 만든다', () => {
    const rows = simulate({ quantity: '10000', prices: ['70000', '75000'], currentPrice: '71500' })
    expect(rows).toHaveLength(2)
    expect(rows[0].revenue).toBe('700000000')
    expect(rows[1].revenue).toBe('750000000')
  })

  it('현재가 대비 증감을 계산한다', () => {
    const rows = simulate({ quantity: '10000', prices: ['75000'], currentPrice: '71500' })
    expect(rows[0].deltaFromCurrent).toBe('35000000')
  })

  it('현재가보다 낮으면 음수 증감', () => {
    const rows = simulate({ quantity: '10000', prices: ['70000'], currentPrice: '71500' })
    expect(rows[0].deltaFromCurrent).toBe('-15000000')
  })

  it('현재가가 없으면 증감은 null이고 매출은 계산된다', () => {
    const rows = simulate({ quantity: '10000', prices: ['70000'], currentPrice: null })
    expect(rows[0].revenue).toBe('700000000')
    expect(rows[0].deltaFromCurrent).toBeNull()
  })

  it('가격 목록이 비면 빈 배열', () => {
    expect(simulate({ quantity: '10000', prices: [], currentPrice: '71500' })).toEqual([])
  })

  it('잘못된 가격은 건너뛴다', () => {
    const rows = simulate({ quantity: '10000', prices: ['70000', 'abc'], currentPrice: null })
    expect(rows).toHaveLength(1)
  })
})

describe('simulateTranches', () => {
  const tranches = [
    { quantity: '3000', price: '72000' },
    { quantity: '3000', price: '75000' },
    { quantity: '4000', price: '78000' },
  ]

  it('총 수량과 총 매출을 계산한다', () => {
    const result = simulateTranches(tranches)
    expect(result.totalQuantity).toBe('10000')
    expect(result.totalRevenue).toBe('753000000')
  })

  it('평균 매도가는 수량 가중평균이다', () => {
    // 단순 산술평균은 75000이지만 가중평균은 75300이다.
    const result = simulateTranches(tranches)
    expect(result.averagePrice).toBe('75300')
  })

  it('각 회차 매출을 낸다', () => {
    const result = simulateTranches(tranches)
    expect(result.rows.map((row) => row.revenue)).toEqual(['216000000', '225000000', '312000000'])
  })

  it('빈 목록이면 0이고 평균가는 null', () => {
    const result = simulateTranches([])
    expect(result.totalQuantity).toBe('0')
    expect(result.totalRevenue).toBe('0')
    expect(result.averagePrice).toBeNull()
  })

  it('총 수량이 0이면 평균가는 null이다', () => {
    // 0으로 나누어 Infinity나 NaN을 만들지 않는다.
    const result = simulateTranches([{ quantity: '0', price: '72000' }])
    expect(result.averagePrice).toBeNull()
  })
})
