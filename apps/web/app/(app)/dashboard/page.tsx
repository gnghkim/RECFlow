import { Card, CardTitle } from '@/components/ui/card'
import { Stat } from '@/components/ui/stat'
import { Empty } from '@/components/ui/empty'
import { Badge } from '@/components/ui/badge'
import { PriceChart } from '@/components/charts/price-chart'
import { getMarketHistory, getMarketStats } from '@/lib/queries/market'
import { getActiveTargets, getHoldingsSummary } from '@/lib/queries/company'
import { MA_WINDOWS, movingAverage } from '@/lib/analytics/ma'
import { percentile, priceBand } from '@/lib/analytics/percentile'
import { decisionScore } from '@/lib/analytics/score'
import { valuation } from '@/lib/analytics/valuation'
import { DASH, formatKrw, formatPercent, formatQuantity } from '@/lib/money'
import { resolvePeriod } from '@/lib/period'

export default async function DashboardPage() {
  const [stats, holdings, targets] = await Promise.all([
    getMarketStats(),
    getHoldingsSummary(),
    getActiveTargets(),
  ])

  if (!stats.latest) {
    return (
      <Empty
        title="수집된 REC 시세가 없습니다"
        hint="수집 상태 화면에서 수동 수집을 실행하거나, 수집기가 정상 동작하는지 확인하세요."
      />
    )
  }

  const yearAgo = resolvePeriod('1Y').from
  const history = await getMarketHistory({ from: yearAgo })
  const prices = history.map((point) => point.avgPrice)

  // 이동평균은 한 번만 계산한다. map 안에서 다시 부르면 313일 × 3계열이
  // 매 인덱스마다 재계산되어 O(n²)가 된다.
  const ma8Series = movingAverage(prices, MA_WINDOWS.MA8)
  const ma26Series = movingAverage(prices, MA_WINDOWS.MA26)
  const ma52Series = movingAverage(prices, MA_WINDOWS.MA52)

  const ma8 = ma8Series.at(-1) ?? null
  const ma26 = ma26Series.at(-1) ?? null
  const ma52 = ma52Series.at(-1) ?? null

  const window = prices.filter((price): price is number => price !== null)
  const current = stats.latest.avgPrice
  const percentileValue = current === null ? null : percentile(current, window)
  const band = priceBand(percentileValue)

  const volumes = history.map((point) => point.volume).filter((v): v is number => v !== null)
  const recentVolumes = volumes.slice(-26)
  const averageVolume3m =
    recentVolumes.length > 0
      ? recentVolumes.reduce((sum, value) => sum + value, 0) / recentVolumes.length
      : null

  const score = decisionScore({
    percentile: percentileValue,
    currentPrice: current,
    ma8,
    ma26,
    recentVolume: stats.latest.volume,
    averageVolume3m,
  })

  const evaluated = valuation({ holdings: holdings.holdings, unitPrice: current?.toString() ?? null })

  const chartData = history.map((point, index) => ({
    tradeDate: point.tradeDate,
    avgPrice: point.avgPrice,
    ma8: ma8Series[index],
    ma26: ma26Series[index],
    ma52: ma52Series[index],
  }))

  const changeTone = stats.changeRate === null ? 'neutral' : stats.changeRate >= 0 ? 'up' : 'down'

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">REC 시장</h1>
        <p className="mt-1 text-sm text-[var(--color-muted)]">
          최근 거래일 {stats.latest.tradeDate}
        </p>
      </div>

      <Card>
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="평균가" value={formatKrw(stats.latest.avgPrice)} />
          <Stat label="종가" value={formatKrw(stats.latest.closePrice)} />
          <Stat label="거래량" value={formatQuantity(stats.latest.volume)} sub="REC" />
          <Stat
            label="전 거래일 대비"
            value={formatPercent(stats.changeRate)}
            tone={changeTone}
          />
        </div>
      </Card>

      <Card>
        <CardTitle>최근 1년 가격 추이</CardTitle>
        <div className="mt-4">
          <PriceChart data={chartData} />
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardTitle>보유 REC</CardTitle>
          {holdings.byPlant.length === 0 ? (
            <div className="mt-4">
              <Empty title="등록된 발전소가 없습니다" hint="보유 REC 화면에서 발전소를 먼저 등록하세요." />
            </div>
          ) : (
            <div className="mt-4 grid gap-6 sm:grid-cols-3">
              <Stat label="보유량" value={formatQuantity(holdings.holdings)} sub="REC" />
              <Stat label="현재 평가액" value={formatKrw(evaluated.amount, { compact: true })} />
              <Stat
                label="목표가격"
                value={targets.length === 0 ? DASH : formatKrw(targets[0].targetPrice)}
                sub={targets.length === 0 ? '미설정' : targets[0].name}
              />
            </div>
          )}
        </Card>

        <Card>
          <CardTitle>매각 판단</CardTitle>
          <div className="mt-4 space-y-3">
            <Row
              label="가격 위치"
              value={band?.label ?? DASH}
              detail={percentileValue === null ? '표본 부족' : `상위 ${formatPercent(100 - percentileValue, 0)}`}
              score={score.breakdown.position}
            />
            <Row
              label="추세"
              value={trendLabel(score.breakdown.trend)}
              detail={ma26 === null ? 'MA26 계산 불가' : `MA8 ${formatKrw(ma8)} / MA26 ${formatKrw(ma26)}`}
              score={score.breakdown.trend}
            />
            <Row
              label="거래량"
              value={volumeLabel(score.breakdown.volume)}
              detail={averageVolume3m === null ? '평균 계산 불가' : `3개월 평균 ${formatQuantity(Math.round(averageVolume3m))}`}
              score={score.breakdown.volume}
            />

            <div className="flex items-center justify-between border-t border-[var(--color-line)] pt-3">
              <span className="text-sm font-medium">종합</span>
              <span className="flex items-center gap-2">
                <span className="tabular text-sm text-[var(--color-muted)]">
                  {score.total === null ? DASH : score.total > 0 ? `+${score.total}` : score.total}
                </span>
                <Badge tone={score.total === null ? 'neutral' : score.total >= 2 ? 'up' : score.total <= -2 ? 'down' : 'neutral'}>
                  {score.label}
                </Badge>
              </span>
            </div>

            <p className="text-xs text-[var(--color-muted)]">
              가격 예측이 아니라 내부 매각 의사결정 보조지표입니다. MA52 {formatKrw(ma52)}.
            </p>
          </div>
        </Card>
      </div>
    </div>
  )
}

function Row({
  label,
  value,
  detail,
  score,
}: {
  label: string
  value: string
  detail: string
  score: number | null
}) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <div>
        <p className="text-sm">{label}</p>
        <p className="text-xs text-[var(--color-muted)]">{detail}</p>
      </div>
      <span className="tabular text-sm">
        {value}
        <span className="ml-2 text-[var(--color-muted)]">
          {score === null ? DASH : score > 0 ? `+${score}` : score}
        </span>
      </span>
    </div>
  )
}

function trendLabel(score: number | null): string {
  if (score === null) return DASH
  if (score >= 2) return '상승'
  if (score === 1) return '완만한 상승'
  if (score === 0) return '혼조'
  if (score === -1) return '완만한 하락'
  return '하락'
}

function volumeLabel(score: number | null): string {
  if (score === null) return DASH
  if (score === 1) return '증가'
  if (score === 0) return '보통'
  return '감소'
}
