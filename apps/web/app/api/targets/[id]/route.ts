import { NextResponse } from 'next/server'
import { prisma } from '@/lib/db'
import { parsePositiveInt } from '@/lib/validate'

export async function DELETE(_request: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params
  const parsed = parsePositiveInt(id, '목표가격 ID')
  if (!parsed.ok) return NextResponse.json({ error: parsed.error }, { status: 400 })

  await prisma.priceTarget.delete({ where: { id: parsed.value } })
  return NextResponse.json({ ok: true })
}

export async function PATCH(request: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params
  const parsed = parsePositiveInt(id, '목표가격 ID')
  if (!parsed.ok) return NextResponse.json({ error: parsed.error }, { status: 400 })

  const body = (await request.json().catch(() => null)) as { isActive?: boolean } | null
  if (!body || typeof body.isActive !== 'boolean') {
    return NextResponse.json({ error: 'isActive가 필요합니다.' }, { status: 400 })
  }

  await prisma.priceTarget.update({ where: { id: parsed.value }, data: { isActive: body.isActive } })
  return NextResponse.json({ ok: true })
}
