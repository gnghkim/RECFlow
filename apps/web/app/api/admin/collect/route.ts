import { NextResponse } from 'next/server'
import { parseDateField } from '@/lib/validate'

export async function POST(request: Request) {
  const body = (await request.json().catch(() => null)) as { tradeDate?: string } | null
  const parsed = parseDateField(body?.tradeDate, '거래일')
  if (!parsed.ok) return NextResponse.json({ error: parsed.error }, { status: 400 })

  const base = process.env.COLLECTOR_INTERNAL_URL ?? 'http://collector:8000'

  try {
    const response = await fetch(`${base}/jobs/collect`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ tradeDate: body?.tradeDate }),
      signal: AbortSignal.timeout(60_000),
    })
    const payload = await response.json().catch(() => ({}))
    return NextResponse.json(payload, { status: response.status })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : '수집기에 연결할 수 없습니다.' },
      { status: 502 },
    )
  }
}
