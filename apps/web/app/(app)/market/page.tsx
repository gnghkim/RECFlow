import { Card, CardTitle } from '@/components/ui/card'
import { Empty } from '@/components/ui/empty'
import { Table, Td, Th } from '@/components/ui/table'
import { PeriodTabs } from '@/components/period-tabs'
import { PriceChart } from '@/components/charts/price-chart'
import { VolumeChart } from '@/components/charts/volume-chart'
import { getMarketHistory, getMarketStats } from '@/lib/queries/market'
import { MA_WINDOWS, movingAverage } from '@/lib/analytics/ma'
import { percentile, priceBand } from '@/lib/analytics/percentile'
import { DASH, formatKrw, formatPercent, formatQuantity } from '@/lib/money'
import { resolvePeriod } from '@/lib/period'

export default async function MarketPage({
  searchParams,
}: {
  searchParams: Promise<{ period?: string }>
}) {
  const { period } = await searchParams
  const resolved = resolvePeriod(period)

  const [history, stats] = await Promise.all([
    getMarketHistory({ from: resolved.from }),
    getMarketStats(),
  ])

  if (history.length === 0) {
    return <Empty title="해당 기간에 수집된 데이터가 없습니다" hint="다른 기간을 선택해 보세요." />
  }

  const prices = history.map((point) => point.avgPrice)
  const ma8 = movingAverage(prices, MA_WINDOWS.MA8)
  const ma26 = movingAverage(prices, MA_WINDOWS.MA26)
  const ma52 = movingAverage(prices, MA_WINDOWS.MA52)

  const chartData = history.map((point, index) => ({
    tradeDate: point.tradeDate,
    avgPrice: point.avgPrice,
    ma8: ma8[index],
    ma26: ma26[index],
    ma52: ma52[index],
  }))

  const yearWindow = (await getMarketHistory({ from: resolvePeriod('1Y').from }))
    .map((point) => point.avgPrice)
    .filter((price): price is number => price !== null)

  const current = stats.latest?.avgPrice ?? null
  const percentileValue = current === null ? null : percentile(current, yearWindow)
  const band = priceBand(percentileValue)

  const latest = stats.latest

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">시장분석</h1>
          <p className="mt-1 text-sm text-[var(--color-muted)]">
            {history[0].tradeDate} ~ {history[history.length - 1].tradeDate} · 거래일 {history.length}일
          </p>
        </div>
        <PeriodTabs current={resolved.key} basePath="/market" />
      </div>

      <Card>
        <CardTitle>최근 거래일 지표</CardTitle>
        <div className="mt-4">
          <Table>
            <tbody>
              <MetricRow label="평균가" value={formatKrw(latest?.avgPrice)} />
              <MetricRow label="종가" value={formatKrw(latest?.closePrice)} />
              <MetricRow label="최고가" value={formatKrw(latest?.highPrice)} />
              <MetricRow label="최저가" value={formatKrw(latest?.lowPrice)} />
              <MetricRow label="거래량" value={`${formatQuantity(latest?.volume)} REC`} />
              <MetricRow label="거래금액" value={formatKrw(latest?.tradeAmount, { compact: true })} />
              <MetricRow label="직전 거래일 대비" value={formatPercent(stats.changeRate)} />
              <MetricRow label="1개월 평균 대비" value={compare(current, stats.average1m)} />
              <MetricRow label="3개월 평균 대비" value={compare(current, stats.average3m)} />
              <MetricRow label="1년 평균 대비" value={compare(current, stats.average12m)} />
            </tbody>
          </Table>
        </div>
      </Card>

      <Card>
        <CardTitle>가격과 이동평균</CardTitle>
        <div className="mt-4">
          <PriceChart data={chartData} height={360} />
        </div>
        <p className="mt-2 text-xs text-[var(--color-muted)]">
          주 2회 거래이므로 MA8은 약 1개월, MA26은 약 3개월, MA52는 약 6개월에 해당합니다.
        </p>
      </Card>

      <Card>
        <CardTitle>거래량</CardTitle>
        <div className="mt-4">
          <VolumeChart data={history.map((point) => ({ tradeDate: point.tradeDate, volume: point.volume }))} />
        </div>
      </Card>

      <Card>
        <CardTitle>가격 위치</CardTitle>
        <div className="mt-4 grid gap-6 sm:grid-cols-2">
          <div className="space-y-2 text-sm">
            <Line label="현재 REC" value={formatKrw(current)} />
            <Line label="최근 1개월 평균" value={formatKrw(stats.average1m)} />
            <Line label="최근 3개월 평균" value={formatKrw(stats.average3m)} />
            <Line label="최근 1년 평균" value={formatKrw(stats.average12m)} />
          </div>
          <div className="space-y-2 text-sm">
            <Line label="1년 최고" value={formatKrw(stats.high1y)} />
            <Line label="1년 최저" value={formatKrw(stats.low1y)} />
            <Line
              label="현재 Percentile"
              value={percentileValue === null ? DASH : formatPercent(percentileValue, 0)}
            />
            <Line label="가격 위치" value={band?.label ?? DASH} />
          </div>
        </div>
        {percentileValue === null ? (
          <p className="mt-3 text-xs text-[var(--color-muted)]">
            1년 백분위는 거래일 표본이 26일 이상 쌓여야 계산됩니다.
          </p>
        ) : null}
      </Card>
    </div>
  )
}

function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <tr>
      <Th>{label}</Th>
      <Td align="right">{value}</Td>
    </tr>
  )
}

function Line({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4">
      <span className="text-[var(--color-muted)]">{label}</span>
      <span className="tabular">{value}</span>
    </div>
  )
}

function compare(current: number | null, average: number | null): string {
  if (current === null || average === null || average === 0) return DASH
  return formatPercent(((current - average) / average) * 100)
}
