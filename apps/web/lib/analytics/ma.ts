/**
 * 거래일 인덱스 기준 단순이동평균.
 *
 * REC 현물시장은 주 2회(화·목) 거래되므로 캘린더 기준이 아니라 배열 위치를 센다.
 * MA8이 약 1개월, MA26이 약 3개월, MA52가 약 6개월에 대응한다.
 */
export const MA_WINDOWS = {
  MA4: 4,
  MA8: 8,
  MA26: 26,
  MA52: 52,
  MA104: 104,
} as const

export type MaWindow = keyof typeof MA_WINDOWS

export function movingAverage(series: (number | null)[], window: number): (number | null)[] {
  if (!Number.isInteger(window) || window < 1) {
    throw new Error(`이동평균 창 크기는 1 이상의 정수여야 한다: ${window}`)
  }

  return series.map((_, index) => {
    if (index + 1 < window) return null

    const slice = series.slice(index + 1 - window, index + 1)
    // 결측이 하나라도 있으면 평균을 내지 않는다. 0이나 직전값으로 메우면
    // 지표가 조용히 왜곡되고, 그 왜곡이 매각 판단 점수까지 전파된다.
    if (slice.some((value) => value === null || !Number.isFinite(value))) return null

    const sum = slice.reduce<number>((total, value) => total + (value as number), 0)
    return sum / window
  })
}
