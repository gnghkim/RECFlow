import { NextResponse } from 'next/server'
import { prisma } from '@/lib/db'
import { parseDateField, parseDecimalField, parsePositiveInt } from '@/lib/validate'

export async function GET() {
  const rows = await prisma.recInventory.findMany({
    orderBy: { issueDate: 'desc' },
    include: { plant: { select: { name: true } } },
  })
  return NextResponse.json(
    rows.map((row) => ({
      id: row.id,
      plantId: row.plantId,
      plantName: row.plant.name,
      issueDate: row.issueDate.toISOString().slice(0, 10),
      recQuantity: row.recQuantity.toString(),
      expiredAt: row.expiredAt?.toISOString().slice(0, 10) ?? null,
      memo: row.memo,
    })),
  )
}

export async function POST(request: Request) {
  const body = (await request.json().catch(() => null)) as Record<string, unknown> | null
  if (!body) return NextResponse.json({ error: '요청 본문이 올바르지 않습니다.' }, { status: 400 })

  const plantId = parsePositiveInt(body.plantId, '발전소')
  if (!plantId.ok) return NextResponse.json({ error: plantId.error }, { status: 400 })

  const issueDate = parseDateField(body.issueDate, '발급일')
  if (!issueDate.ok) return NextResponse.json({ error: issueDate.error }, { status: 400 })

  const quantity = parseDecimalField(body.recQuantity, '발급 REC')
  if (!quantity.ok) return NextResponse.json({ error: quantity.error }, { status: 400 })

  const created = await prisma.recInventory.create({
    data: {
      plantId: plantId.value,
      issueDate: issueDate.value,
      recQuantity: quantity.value,
      memo: body.memo ? String(body.memo).trim() : null,
    },
  })

  return NextResponse.json({ id: created.id }, { status: 201 })
}
