import { describe, expect, it } from 'vitest'
import { valuation } from './valuation'

describe('valuation', () => {
  it('보유량 곱하기 시장가격', () => {
    expect(valuation({ holdings: '10000', unitPrice: '71500' }).amount).toBe('715000000')
  })

  it('가격이 없으면 null이다', () => {
    // 수집 데이터가 없을 때 0원이라고 말하지 않는다.
    expect(valuation({ holdings: '10000', unitPrice: null }).amount).toBeNull()
  })

  it('보유량이 0이면 0원', () => {
    expect(valuation({ holdings: '0', unitPrice: '71500' }).amount).toBe('0')
  })

  it('소수 보유량을 정확히 계산한다', () => {
    expect(valuation({ holdings: '1000.55', unitPrice: '71500' }).amount).toBe('71539325')
  })

  it('부동소수점 오차가 생기지 않는다', () => {
    // 0.1 * 3 을 double로 하면 0.30000000000000004 가 된다.
    expect(valuation({ holdings: '0.1', unitPrice: '3' }).amount).toBe('0.3')
  })
})
