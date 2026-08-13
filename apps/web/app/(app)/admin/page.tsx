import { Card, CardTitle } from '@/components/ui/card'
import { Stat } from '@/components/ui/stat'
import { Badge } from '@/components/ui/badge'
import { Empty } from '@/components/ui/empty'
import { Table, Td, Th } from '@/components/ui/table'
import { CollectButton } from './collect-button'
import { getCollectionSummary, getRecentRuns } from '@/lib/queries/collection'
import { DASH } from '@/lib/money'

// dynamic 설정은 (app)/layout.tsx가 하위 전체에 적용하므로 여기 다시 쓰지 않는다.

const STATUS_TONE: Record<string, 'neutral' | 'up' | 'down'> = {
  SUCCESS: 'neutral',
  PARTIAL: 'up',
  NO_DATA: 'neutral',
  FAILED: 'up',
}

export default async function AdminPage() {
  const [summary, runs] = await Promise.all([getCollectionSummary(), getRecentRuns(20)])

  let collectorOk = false
  let collectorError: string | null = null
  try {
    const base = process.env.COLLECTOR_INTERNAL_URL ?? 'http://collector:8000'
    const response = await fetch(`${base}/health`, {
      cache: 'no-store',
      signal: AbortSignal.timeout(3000),
    })
    collectorOk = response.ok
    if (!response.ok) collectorError = `수집기가 ${response.status}를 반환했습니다.`
  } catch (error) {
    collectorError = error instanceof Error ? error.message : '수집기에 연결할 수 없습니다.'
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold tracking-tight">수집 상태</h1>

      <Card>
        <div className="grid gap-6 sm:grid-cols-4">
          <Stat
            label="마지막 성공 수집"
            value={summary.lastSuccessAt ? summary.lastSuccessAt.slice(0, 16).replace('T', ' ') : DASH}
            sub={summary.lastSuccessDate ? `거래일 ${summary.lastSuccessDate}` : null}
          />
          <Stat label="누적 실패" value={String(summary.failureCount)} sub="건" />
          <Stat label="적재 행수" value={summary.marketCount.toLocaleString('ko-KR')} sub="rec_market" />
          <div>
            <p className="text-sm text-[var(--color-muted)]">수집기</p>
            <p className="mt-1">
              <Badge tone={collectorOk ? 'neutral' : 'up'}>{collectorOk ? '정상' : '연결 불가'}</Badge>
            </p>
            {collectorError ? (
              <p className="mt-1 text-xs text-[var(--color-muted)]">{collectorError}</p>
            ) : null}
          </div>
        </div>
      </Card>

      <Card>
        <CardTitle>수동 수집</CardTitle>
        <CollectButton />
        <p className="mt-2 text-xs text-[var(--color-muted)]">
          수집은 웹이 직접 하지 않고 수집기에 위임합니다. 수집기에 닿지 못하면 502가 반환됩니다.
        </p>
      </Card>

      <Card>
        <CardTitle>최근 실행</CardTitle>
        {runs.length === 0 ? (
          <div className="mt-4">
            <Empty title="수집 이력이 없습니다" />
          </div>
        ) : (
          <div className="mt-4">
            <Table>
              <thead>
                <tr>
                  <Th>거래일</Th>
                  <Th>종류</Th>
                  <Th>상태</Th>
                  <Th align="right">적재</Th>
                  <Th align="right">시작</Th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.id}>
                    <Td>{run.targetDate ?? DASH}</Td>
                    <Td>{run.jobType}</Td>
                    <Td>
                      <Badge tone={STATUS_TONE[run.status] ?? 'neutral'}>{run.status}</Badge>
                      {run.errorMessage ? (
                        <span className="ml-2 text-xs text-[var(--color-muted)]">{run.errorMessage}</span>
                      ) : null}
                    </Td>
                    <Td align="right">{run.rowsUpserted}</Td>
                    <Td align="right">{run.startedAt.slice(0, 16).replace('T', ' ')}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>
        )}
      </Card>
    </div>
  )
}
