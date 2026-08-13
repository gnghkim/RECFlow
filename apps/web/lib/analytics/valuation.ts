import { toDecimal } from '@/lib/money'

/**
 * 보유 REC의 현재 평가액.
 *
 * rec_inventory.rec_quantity 는 가중치가 이미 적용된 발급 수량이므로
 * 여기서 가중치를 다시 곱하지 않는다.
 */
export function valuation(input: {
  holdings: string
  unitPrice: string | null
}): { amount: string | null } {
  const holdings = toDecimal(input.holdings)
  const unitPrice = toDecimal(input.unitPrice)

  // 시세가 없을 때 0원이라고 말하지 않는다. 모른다고 말한다.
  if (holdings === null || unitPrice === null) return { amount: null }

  return { amount: holdings.mul(unitPrice).toString() }
}
