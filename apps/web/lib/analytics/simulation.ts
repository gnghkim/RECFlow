import Decimal from 'decimal.js'
import { toDecimal } from '@/lib/money'

export type SimulationRow = {
  price: string
  revenue: string
  deltaFromCurrent: string | null
}

export type TrancheInput = { quantity: string; price: string }
export type TrancheRow = { quantity: string; price: string; revenue: string }

export function simulate(input: {
  quantity: string
  prices: string[]
  currentPrice: string | null
}): SimulationRow[] {
  const quantity = toDecimal(input.quantity)
  if (quantity === null) return []

  const currentPrice = toDecimal(input.currentPrice)
  const currentRevenue = currentPrice === null ? null : quantity.mul(currentPrice)

  return input.prices
    .map((raw) => {
      const price = toDecimal(raw)
      if (price === null) return null

      const revenue = quantity.mul(price)
      return {
        price: price.toString(),
        revenue: revenue.toString(),
        deltaFromCurrent: currentRevenue === null ? null : revenue.minus(currentRevenue).toString(),
      }
    })
    .filter((row): row is SimulationRow => row !== null)
}

export function simulateTranches(tranches: TrancheInput[]): {
  totalQuantity: string
  totalRevenue: string
  averagePrice: string | null
  rows: TrancheRow[]
} {
  const rows: TrancheRow[] = []
  let totalQuantity = new Decimal(0)
  let totalRevenue = new Decimal(0)

  for (const tranche of tranches) {
    const quantity = toDecimal(tranche.quantity)
    const price = toDecimal(tranche.price)
    if (quantity === null || price === null) continue

    const revenue = quantity.mul(price)
    rows.push({ quantity: quantity.toString(), price: price.toString(), revenue: revenue.toString() })
    totalQuantity = totalQuantity.plus(quantity)
    totalRevenue = totalRevenue.plus(revenue)
  }

  // 회차별 수량이 다르면 산술평균은 틀린다. 수량 가중평균을 쓴다.
  // 총 수량이 0이면 나눌 수 없으므로 null이다. Infinity나 NaN을 만들지 않는다.
  const averagePrice = totalQuantity.isZero() ? null : totalRevenue.div(totalQuantity).toString()

  return {
    totalQuantity: totalQuantity.toString(),
    totalRevenue: totalRevenue.toString(),
    averagePrice,
    rows,
  }
}
