import Decimal from 'decimal.js'
import { prisma } from '@/lib/db'
import type { PlantHolding } from '@/lib/types'

/**
 * 보유량은 저장하지 않고 계산한다.
 *   발급 = Σ rec_inventory.rec_quantity (expired_at IS NULL)
 *   매각 = Σ rec_sales.quantity
 *   보유 = 발급 − 매각
 * 상태 컬럼을 두면 부분 매각을 표현할 수 없고 매각 내역과 어긋난다.
 */
export async function getHoldingsSummary(): Promise<{
  issued: string
  sold: string
  holdings: string
  byPlant: PlantHolding[]
}> {
  const [plants, issuedRows, soldRows] = await Promise.all([
    prisma.plant.findMany({ orderBy: { name: 'asc' }, select: { id: true, name: true } }),
    prisma.recInventory.groupBy({
      by: ['plantId'],
      where: { expiredAt: null },
      _sum: { recQuantity: true },
    }),
    prisma.recSale.groupBy({ by: ['plantId'], _sum: { quantity: true } }),
  ])

  const issuedByPlant = new Map(issuedRows.map((row) => [row.plantId, row._sum.recQuantity]))
  const soldByPlant = new Map(soldRows.map((row) => [row.plantId, row._sum.quantity]))

  let totalIssued = new Decimal(0)
  let totalSold = new Decimal(0)

  const byPlant: PlantHolding[] = plants.map((plant) => {
    const issued = new Decimal(issuedByPlant.get(plant.id)?.toString() ?? '0')
    const sold = new Decimal(soldByPlant.get(plant.id)?.toString() ?? '0')
    totalIssued = totalIssued.plus(issued)
    totalSold = totalSold.plus(sold)

    return {
      plantId: plant.id,
      plantName: plant.name,
      issued: issued.toString(),
      sold: sold.toString(),
      holdings: issued.minus(sold).toString(),
    }
  })

  return {
    issued: totalIssued.toString(),
    sold: totalSold.toString(),
    holdings: totalIssued.minus(totalSold).toString(),
    byPlant,
  }
}

export async function getActiveTargets() {
  const targets = await prisma.priceTarget.findMany({
    where: { isActive: true },
    orderBy: { targetPrice: 'asc' },
  })
  return targets.map((target) => ({
    id: target.id,
    name: target.name,
    targetPrice: target.targetPrice.toString(),
  }))
}
