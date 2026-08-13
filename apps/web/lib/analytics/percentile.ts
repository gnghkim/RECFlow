/**
 * 현재 가격이 과거 분포에서 어디에 있는지 나타낸다.
 *
 * 미래 예측이 아니라 위치 확인이다. 표본이 적으면 위치를 말할 수 없으므로
 * null을 반환한다. 시스템 가동 초기에는 이 값이 없는 것이 정상이다.
 */
export const MIN_PERCENTILE_SAMPLES = 26

export function percentile(current: number, window: number[]): number | null {
  const samples = window.filter((value) => Number.isFinite(value))
  if (samples.length === 0 || samples.length < MIN_PERCENTILE_SAMPLES) return null

  const atOrBelow = samples.filter((value) => value <= current).length
  return (atOrBelow / samples.length) * 100
}

export type PriceBand = { key: 'very-low' | 'low' | 'normal' | 'high' | 'very-high'; label: string }

const BANDS: { min: number; band: PriceBand }[] = [
  { min: 80, band: { key: 'very-high', label: '매우 높음' } },
  { min: 60, band: { key: 'high', label: '높음' } },
  { min: 40, band: { key: 'normal', label: '보통' } },
  { min: 20, band: { key: 'low', label: '낮음' } },
  { min: 0, band: { key: 'very-low', label: '매우 낮음' } },
]

export function priceBand(percentileValue: number | null): PriceBand | null {
  if (percentileValue === null || !Number.isFinite(percentileValue)) return null
  return BANDS.find(({ min }) => percentileValue >= min)?.band ?? null
}
