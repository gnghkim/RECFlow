import { NextResponse } from 'next/server'
import { prisma } from '@/lib/db'
import { parseDecimalField } from '@/lib/validate'

export async function GET() {
  const plants = await prisma.plant.findMany({ orderBy: { name: 'asc' } })
  return NextResponse.json(
    plants.map((plant) => ({
      id: plant.id,
      name: plant.name,
      location: plant.location,
      capacityKw: plant.capacityKw?.toString() ?? null,
      recWeight: plant.recWeight?.toString() ?? null,
      isActive: plant.isActive,
    })),
  )
}

export async function POST(request: Request) {
  const body = (await request.json().catch(() => null)) as Record<string, unknown> | null
  if (!body) return NextResponse.json({ error: '요청 본문이 올바르지 않습니다.' }, { status: 400 })

  const name = String(body.name ?? '').trim()
  if (name.length === 0) return NextResponse.json({ error: '발전소명을 입력하세요.' }, { status: 400 })

  const capacity = body.capacityKw ? parseDecimalField(body.capacityKw, '설비용량') : null
  if (capacity && !capacity.ok) return NextResponse.json({ error: capacity.error }, { status: 400 })

  const weight = body.recWeight ? parseDecimalField(body.recWeight, 'REC 가중치') : null
  if (weight && !weight.ok) return NextResponse.json({ error: weight.error }, { status: 400 })

  const plant = await prisma.plant.create({
    data: {
      name,
      location: body.location ? String(body.location).trim() : null,
      capacityKw: capacity?.ok ? capacity.value : null,
      recWeight: weight?.ok ? weight.value : null,
    },
  })

  return NextResponse.json({ id: plant.id }, { status: 201 })
}
