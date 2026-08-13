import { NextResponse, type NextRequest } from 'next/server'
import { getMarketHistory } from '@/lib/queries/market'
import { resolvePeriod } from '@/lib/period'
import type { MarketArea } from '@/lib/types'

const AREAS: MarketArea[] = ['LAND', 'JEJU', 'TOTAL']

export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams
  const { key, from } = resolvePeriod(params.get('period') ?? undefined)

  const requestedArea = params.get('area') as MarketArea | null
  const area = requestedArea && AREAS.includes(requestedArea) ? requestedArea : 'TOTAL'

  const points = await getMarketHistory({ from, area })
  return NextResponse.json({ period: key, area, count: points.length, points })
}
