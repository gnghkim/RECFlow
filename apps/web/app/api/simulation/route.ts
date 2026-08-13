import { NextResponse } from 'next/server'
import { simulate, simulateTranches } from '@/lib/analytics/simulation'
import { DECIMAL_LIMITS, parseDecimalField } from '@/lib/validate'

export async function POST(request: Request) {
  const body = (await request.json().catch(() => null)) as Record<string, unknown> | null
  if (!body) return NextResponse.json({ error: '요청 본문이 올바르지 않습니다.' }, { status: 400 })

  if (body.mode === 'tranches') {
    const raw = Array.isArray(body.tranches) ? body.tranches : []
    const tranches: { quantity: string; price: string }[] = []

    for (const [index, item] of raw.entries()) {
      const entry = item as Record<string, unknown>
      const quantity = parseDecimalField(entry.quantity, `${index + 1}차 수량`, { max: DECIMAL_LIMITS.quantity })
      if (!quantity.ok) return NextResponse.json({ error: quantity.error }, { status: 400 })
      const price = parseDecimalField(entry.price, `${index + 1}차 가격`, { max: DECIMAL_LIMITS.price })
      if (!price.ok) return NextResponse.json({ error: price.error }, { status: 400 })
      tranches.push({ quantity: quantity.value, price: price.value })
    }

    return NextResponse.json(simulateTranches(tranches))
  }

  const quantity = parseDecimalField(body.quantity, '보유량', { max: DECIMAL_LIMITS.quantity })
  if (!quantity.ok) return NextResponse.json({ error: quantity.error }, { status: 400 })

  const prices = Array.isArray(body.prices) ? body.prices.map((price) => String(price)) : []
  const currentPrice = body.currentPrice === null || body.currentPrice === undefined
    ? null
    : String(body.currentPrice)

  return NextResponse.json({ rows: simulate({ quantity: quantity.value, prices, currentPrice }) })
}
