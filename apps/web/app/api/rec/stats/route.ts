import { NextResponse } from 'next/server'
import { getMarketStats } from '@/lib/queries/market'

export async function GET() {
  return NextResponse.json(await getMarketStats())
}
