import { NextResponse } from 'next/server'
import { prisma } from '@/lib/db'
import { parsePositiveInt } from '@/lib/validate'

export async function DELETE(_request: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params
  const parsed = parsePositiveInt(id, '발급 ID')
  if (!parsed.ok) return NextResponse.json({ error: parsed.error }, { status: 400 })

  await prisma.recInventory.delete({ where: { id: parsed.value } })
  return NextResponse.json({ ok: true })
}
