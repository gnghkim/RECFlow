import { Card } from '@/components/ui/card'
import { Empty } from '@/components/ui/empty'
import { SimulationPanel } from './simulation-panel'
import { getHoldingsSummary } from '@/lib/queries/company'
import { getLatestMarket } from '@/lib/queries/market'

export default async function SimulationPage() {
  const [summary, latest] = await Promise.all([getHoldingsSummary(), getLatestMarket()])

  if (summary.holdings === '0') {
    return (
      <Empty
        title="보유 중인 REC가 없습니다"
        hint="보유 REC 화면에서 발전소와 발급 내역을 먼저 등록하세요."
      />
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">매각 시뮬레이션</h1>
        <p className="mt-1 text-sm text-[var(--color-muted)]">
          보유 {summary.holdings} REC
          {latest?.avgPrice ? ` · 현재가 ${latest.avgPrice.toLocaleString('ko-KR')}원` : ''}
        </p>
      </div>
      <Card>
        <SimulationPanel
          holdings={summary.holdings}
          currentPrice={latest?.avgPrice?.toString() ?? null}
        />
      </Card>
    </div>
  )
}
