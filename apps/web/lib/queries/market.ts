import type { Prisma } from '@prisma/client'
import { prisma } from '@/lib/db'
import type { MarketArea, MarketPoint, MarketStats } from '@/lib/types'

type MarketRow = {
  tradeDate: Date
  avgPrice: Prisma.Decimal | null
  closePrice: Prisma.Decimal | null
  highPrice: Prisma.Decimal | null
  lowPrice: Prisma.Decimal | null
  volume: Prisma.Decimal | null
  tradeAmount: Prisma.Decimal | null
  tradeCount: number | null
}

/** Decimal이 화면으로 새어나가지 않게 막는 유일한 지점이다. */
function toPoint(row: MarketRow): MarketPoint {
  return {
    tradeDate: row.tradeDate.toISOString().slice(0, 10),
    avgPrice: row.avgPrice === null ? null : row.avgPrice.toNumber(),
    closePrice: row.closePrice === null ? null : row.closePrice.toNumber(),
    highPrice: row.highPrice === null ? null : row.highPrice.toNumber(),
    lowPrice: row.lowPrice === null ? null : row.lowPrice.toNumber(),
    volume: row.volume === null ? null : row.volume.toNumber(),
    tradeAmount: row.tradeAmount === null ? null : row.tradeAmount.toString(),
    tradeCount: row.tradeCount,
  }
}

const SELECT = {
  tradeDate: true,
  avgPrice: true,
  closePrice: true,
  highPrice: true,
  lowPrice: true,
  volume: true,
  tradeAmount: true,
  tradeCount: true,
} as const

export async function getLatestMarket(area: MarketArea = 'TOTAL'): Promise<MarketPoint | null> {
  const row = await prisma.recMarket.findFirst({
    where: { marketArea: area },
    orderBy: { tradeDate: 'desc' },
    select: SELECT,
  })
  return row ? toPoint(row) : null
}

export async function getMarketHistory(options: {
  from?: Date | null
  to?: Date | null
  area?: MarketArea
} = {}): Promise<MarketPoint[]> {
  const rows = await prisma.recMarket.findMany({
    where: {
      marketArea: options.area ?? 'TOTAL',
      ...(options.from || options.to
        ? {
            tradeDate: {
              ...(options.from ? { gte: options.from } : {}),
              ...(options.to ? { lte: options.to } : {}),
            },
          }
        : {}),
    },
    orderBy: { tradeDate: 'asc' },
    select: SELECT,
  })
  return rows.map(toPoint)
}

export async function getMarketStats(today: Date = new Date()): Promise<MarketStats> {
  const recent = await prisma.recMarket.findMany({
    where: { marketArea: 'TOTAL' },
    orderBy: { tradeDate: 'desc' },
    take: 2,
    select: SELECT,
  })

  const latest = recent[0] ? toPoint(recent[0]) : null
  const previous = recent[1] ? toPoint(recent[1]) : null

  const changeRate =
    latest?.avgPrice != null && previous?.avgPrice != null && previous.avgPrice !== 0
      ? ((latest.avgPrice - previous.avgPrice) / previous.avgPrice) * 100
      : null

  const [average1m, average3m, average12m] = await Promise.all([
    averageSince(monthsAgo(today, 1)),
    averageSince(monthsAgo(today, 3)),
    averageSince(monthsAgo(today, 12)),
  ])

  const range = await prisma.recMarket.aggregate({
    where: { marketArea: 'TOTAL', tradeDate: { gte: monthsAgo(today, 12) } },
    _max: { avgPrice: true },
    _min: { avgPrice: true },
  })

  return {
    latest,
    previous,
    changeRate,
    average1m,
    average3m,
    average12m,
    high1y: range._max.avgPrice?.toNumber() ?? null,
    low1y: range._min.avgPrice?.toNumber() ?? null,
  }
}

async function averageSince(from: Date): Promise<number | null> {
  const result = await prisma.recMarket.aggregate({
    where: { marketArea: 'TOTAL', tradeDate: { gte: from } },
    _avg: { avgPrice: true },
  })
  return result._avg.avgPrice?.toNumber() ?? null
}

function monthsAgo(today: Date, months: number): Date {
  const date = new Date(today)
  date.setUTCMonth(date.getUTCMonth() - months)
  return date
}
