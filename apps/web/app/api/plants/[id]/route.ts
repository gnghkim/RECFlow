import { NextResponse } from 'next/server'
import { prisma } from '@/lib/db'
import { parsePositiveInt } from '@/lib/validate'

export async function DELETE(_request: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params
  const parsed = parsePositiveInt(id, '발전소 ID')
  if (!parsed.ok) return NextResponse.json({ error: parsed.error }, { status: 400 })

  const [inventoryCount, saleCount] = await Promise.all([
    prisma.recInventory.count({ where: { plantId: parsed.value } }),
    prisma.recSale.count({ where: { plantId: parsed.value } }),
  ])

  // 발급이나 매각 기록이 있으면 지우지 않는다. 지우면 과거 집계가 바뀐다.
  if (inventoryCount > 0 || saleCount > 0) {
    return NextResponse.json(
      { error: '발급 또는 매각 기록이 있어 삭제할 수 없습니다. 비활성으로 바꾸세요.' },
      { status: 409 },
    )
  }

  await prisma.plant.delete({ where: { id: parsed.value } })
  return NextResponse.json({ ok: true })
}

export async function PATCH(request: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params
  const parsed = parsePositiveInt(id, '발전소 ID')
  if (!parsed.ok) return NextResponse.json({ error: parsed.error }, { status: 400 })

  const body = (await request.json().catch(() => null)) as { isActive?: boolean } | null
  if (!body || typeof body.isActive !== 'boolean') {
    return NextResponse.json({ error: 'isActive가 필요합니다.' }, { status: 400 })
  }

  await prisma.plant.update({ where: { id: parsed.value }, data: { isActive: body.isActive } })
  return NextResponse.json({ ok: true })
}
