import { NextResponse } from 'next/server'
import { prisma } from '@/lib/db'
import { DECIMAL_LIMITS, parseDecimalField } from '@/lib/validate'

export async function GET() {
  const targets = await prisma.priceTarget.findMany({ orderBy: { targetPrice: 'asc' } })
  return NextResponse.json(
    targets.map((target) => ({
      id: target.id,
      name: target.name,
      targetPrice: target.targetPrice.toString(),
      isActive: target.isActive,
    })),
  )
}

export async function POST(request: Request) {
  const body = (await request.json().catch(() => null)) as Record<string, unknown> | null
  if (!body) return NextResponse.json({ error: '요청 본문이 올바르지 않습니다.' }, { status: 400 })

  const name = String(body.name ?? '').trim()
  if (name.length === 0) return NextResponse.json({ error: '이름을 입력하세요.' }, { status: 400 })

  const price = parseDecimalField(body.targetPrice, '목표가격', { max: DECIMAL_LIMITS.price })
  if (!price.ok) return NextResponse.json({ error: price.error }, { status: 400 })

  const created = await prisma.priceTarget.create({
    data: { name, targetPrice: price.value },
  })
  return NextResponse.json({ id: created.id }, { status: 201 })
}
