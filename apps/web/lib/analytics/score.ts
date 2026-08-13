/**
 * 매각 판단 보조지표.
 *
 * 가격 예측 모델이 아니다. 가격 위치·추세·거래량이라는 세 가지 관찰 가능한
 * 사실을 규칙으로 점수화해 "왜 이 점수인지" 설명할 수 있게 한 것이다.
 * 회사 내부 매각 의사결정의 참고자료로만 쓴다.
 *
 * 구성요소 중 하나라도 계산할 수 없으면 총점을 내지 않는다. 모르는 것을
 * 0으로 채워 그럴듯한 총점을 만드는 것이 이 시스템의 가장 나쁜 실패다.
 */

export type ScoreInput = {
  percentile: number | null
  currentPrice: number | null
  ma8: number | null
  ma26: number | null
  recentVolume: number | null
  averageVolume3m: number | null
}

export type ScoreBreakdown = {
  position: number | null
  trend: number | null
  volume: number | null
}

export type ScoreResult = {
  total: number | null
  breakdown: ScoreBreakdown
  label: string
  complete: boolean
}

export const INSUFFICIENT_LABEL = '데이터 부족'

const VOLUME_SURGE_RATIO = 1.2
const VOLUME_SLUMP_RATIO = 0.7

export function decisionScore(input: ScoreInput): ScoreResult {
  const breakdown: ScoreBreakdown = {
    position: positionScore(input.percentile),
    trend: trendScore(input.currentPrice, input.ma8, input.ma26),
    volume: volumeScore(input.recentVolume, input.averageVolume3m),
  }

  const parts = [breakdown.position, breakdown.trend, breakdown.volume]
  const complete = parts.every((value) => value !== null)

  if (!complete) {
    return { total: null, breakdown, label: INSUFFICIENT_LABEL, complete: false }
  }

  const total = parts.reduce<number>((sum, value) => sum + (value as number), 0)
  return { total, breakdown, label: labelFor(total), complete: true }
}

function positionScore(percentileValue: number | null): number | null {
  if (percentileValue === null || !Number.isFinite(percentileValue)) return null
  if (percentileValue >= 80) return 2
  if (percentileValue >= 60) return 1
  if (percentileValue >= 40) return 0
  if (percentileValue >= 20) return -1
  return -2
}

function trendScore(current: number | null, ma8: number | null, ma26: number | null): number | null {
  if (current === null || ma26 === null) return null

  if (ma8 !== null && current > ma8 && ma8 > ma26) return 2
  if (current > ma26) return 1
  if (ma8 !== null && current < ma8 && ma8 < ma26) return -2
  if (current < ma26) return -1
  return 0
}

function volumeScore(recent: number | null, average: number | null): number | null {
  if (recent === null || average === null || !Number.isFinite(average) || average <= 0) return null

  const ratio = recent / average
  if (ratio >= VOLUME_SURGE_RATIO) return 1
  if (ratio < VOLUME_SLUMP_RATIO) return -1
  return 0
}

function labelFor(total: number): string {
  if (total >= 4) return '적극 매도 검토'
  if (total >= 2) return '일부 매도 검토'
  if (total >= -1) return '관망'
  return '매도 신중'
}
