import Decimal from 'decimal.js'
import { NextResponse } from 'next/server'
import { prisma } from '@/lib/db'
import { DECIMAL_LIMITS, parseDateField, parseDecimalField, parsePositiveInt } from '@/lib/validate'

export async function GET() {
  const rows = await prisma.recSale.findMany({
    orderBy: { saleDate: 'desc' },
    include: { plant: { select: { name: true } } },
  })
  return NextResponse.json(
    rows.map((row) => ({
      id: row.id,
      plantId: row.plantId,
      plantName: row.plant.name,
      saleDate: row.saleDate.toISOString().slice(0, 10),
      quantity: row.quantity.toString(),
      unitPrice: row.unitPrice.toString(),
      saleAmount: row.saleAmount.toString(),
      buyer: row.buyer,
    })),
  )
}

export async function POST(request: Request) {
  const body = (await request.json().catch(() => null)) as Record<string, unknown> | null
  if (!body) return NextResponse.json({ error: '요청 본문이 올바르지 않습니다.' }, { status: 400 })

  const plantId = parsePositiveInt(body.plantId, '발전소')
  if (!plantId.ok) return NextResponse.json({ error: plantId.error }, { status: 400 })

  const saleDate = parseDateField(body.saleDate, '매각일')
  if (!saleDate.ok) return NextResponse.json({ error: saleDate.error }, { status: 400 })

  const quantity = parseDecimalField(body.quantity, '매각 수량', { max: DECIMAL_LIMITS.quantity })
  if (!quantity.ok) return NextResponse.json({ error: quantity.error }, { status: 400 })

  const unitPrice = parseDecimalField(body.unitPrice, '단가', { max: DECIMAL_LIMITS.price })
  if (!unitPrice.ok) return NextResponse.json({ error: unitPrice.error }, { status: 400 })

  const [issuedAgg, soldAgg] = await Promise.all([
    prisma.recInventory.aggregate({
      where: { plantId: plantId.value, expiredAt: null },
      _sum: { recQuantity: true },
    }),
    prisma.recSale.aggregate({ where: { plantId: plantId.value }, _sum: { quantity: true } }),
  ])

  const issued = new Decimal(issuedAgg._sum.recQuantity?.toString() ?? '0')
  const sold = new Decimal(soldAgg._sum.quantity?.toString() ?? '0')
  const available = issued.minus(sold)
  const requested = new Decimal(quantity.value)

  if (requested.gt(available)) {
    return NextResponse.json(
      { error: `보유량(${available.toString()} REC)보다 많이 매각할 수 없습니다.` },
      { status: 409 },
    )
  }

  const amount = body.saleAmount
    ? parseDecimalField(body.saleAmount, '매각금액', { max: DECIMAL_LIMITS.amount })
    : { ok: true as const, value: requested.mul(new Decimal(unitPrice.value)).toString() }
  if (!amount.ok) return NextResponse.json({ error: amount.error }, { status: 400 })

  const created = await prisma.recSale.create({
    data: {
      plantId: plantId.value,
      saleDate: saleDate.value,
      quantity: quantity.value,
      unitPrice: unitPrice.value,
      saleAmount: amount.value,
      buyer: body.buyer ? String(body.buyer).trim() : null,
      memo: body.memo ? String(body.memo).trim() : null,
    },
  })

  return NextResponse.json({ id: created.id }, { status: 201 })
}
