export type MarketArea = 'LAND' | 'JEJU' | 'TOTAL'

/**
 * Prisma의 Decimal은 JSON 직렬화도 Server → Client 전달도 되지 않는다.
 * lib/queries 가 이 타입으로 변환한 뒤에야 화면으로 나간다.
 *
 * 가격과 거래량은 차트 좌표 계산에 쓰이므로 number,
 * 거래금액은 조 단위까지 커질 수 있어 문자열로 둔다.
 */
export type MarketPoint = {
  tradeDate: string
  avgPrice: number | null
  closePrice: number | null
  highPrice: number | null
  lowPrice: number | null
  volume: number | null
  tradeAmount: string | null
  tradeCount: number | null
}

export type MarketStats = {
  latest: MarketPoint | null
  previous: MarketPoint | null
  changeRate: number | null
  average1m: number | null
  average3m: number | null
  average12m: number | null
  high1y: number | null
  low1y: number | null
}

export type PlantHolding = {
  plantId: number
  plantName: string
  issued: string
  sold: string
  holdings: string
}
