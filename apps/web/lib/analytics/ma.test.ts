import { describe, expect, it } from 'vitest'
import { movingAverage } from './ma'

describe('movingAverage', () => {
  it('창 길이만큼 쌓이기 전에는 null이다', () => {
    expect(movingAverage([1, 2, 3], 4)).toEqual([null, null, null])
  })

  it('창이 채워진 시점부터 값을 낸다', () => {
    expect(movingAverage([1, 2, 3, 4], 4)).toEqual([null, null, null, 2.5])
  })

  it('창이 이동한다', () => {
    expect(movingAverage([1, 2, 3, 4, 5], 2)).toEqual([null, 1.5, 2.5, 3.5, 4.5])
  })

  it('빈 배열은 빈 배열이다', () => {
    expect(movingAverage([], 4)).toEqual([])
  })

  it('창 안에 null이 있으면 그 구간은 null이다', () => {
    // 결측을 0이나 직전값으로 메우면 평균이 조용히 왜곡된다.
    expect(movingAverage([1, null, 3, 4], 2)).toEqual([null, null, null, 3.5])
  })

  it('창 크기가 1보다 작으면 예외', () => {
    expect(() => movingAverage([1, 2], 0)).toThrow()
  })

  it('입력 배열을 변경하지 않는다', () => {
    const input = [1, 2, 3]
    movingAverage(input, 2)
    expect(input).toEqual([1, 2, 3])
  })

  it('거래일 인덱스 기준이므로 날짜 간격과 무관하다', () => {
    // 주 2회 거래이므로 캘린더 기준이 아니라 배열 위치 기준이다.
    expect(movingAverage([10, 20, 30, 40], 2)).toEqual([null, 15, 25, 35])
  })
})
