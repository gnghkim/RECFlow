import { NextResponse } from 'next/server'
import { getLatestMarket } from '@/lib/queries/market'

export async function GET() {
  const latest = await getLatestMarket()
  if (!latest) return NextResponse.json({ error: '수집된 데이터가 없다' }, { status: 404 })
  return NextResponse.json(latest)
}
