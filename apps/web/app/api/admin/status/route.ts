import { NextResponse } from 'next/server'
import { getCollectionSummary } from '@/lib/queries/collection'

export async function GET() {
  const summary = await getCollectionSummary()

  let collector: unknown = null
  let collectorError: string | null = null

  try {
    const base = process.env.COLLECTOR_INTERNAL_URL ?? 'http://collector:8000'
    const response = await fetch(`${base}/health`, {
      cache: 'no-store',
      signal: AbortSignal.timeout(3000),
    })
    collector = response.ok ? await response.json() : null
    if (!response.ok) collectorError = `수집기가 ${response.status}를 반환했습니다.`
  } catch (error) {
    // 수집기에 닿지 못해도 DB 요약은 보여준다.
    collectorError = error instanceof Error ? error.message : '수집기에 연결할 수 없습니다.'
  }

  return NextResponse.json({ ...summary, collector, collectorError })
}
