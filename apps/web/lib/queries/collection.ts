import { prisma } from '@/lib/db'

export type CollectionRunView = {
  id: number
  jobType: string
  targetDate: string | null
  status: string
  rowsUpserted: number
  errorMessage: string | null
  startedAt: string
  finishedAt: string | null
}

export async function getRecentRuns(limit = 20): Promise<CollectionRunView[]> {
  const runs = await prisma.collectionRun.findMany({
    orderBy: { startedAt: 'desc' },
    take: limit,
  })
  return runs.map((run) => ({
    id: run.id,
    jobType: run.jobType,
    targetDate: run.targetDate?.toISOString().slice(0, 10) ?? null,
    status: run.status,
    rowsUpserted: run.rowsUpserted,
    errorMessage: run.errorMessage,
    startedAt: run.startedAt.toISOString(),
    finishedAt: run.finishedAt?.toISOString() ?? null,
  }))
}

export async function getCollectionSummary() {
  const [lastSuccess, failureCount, marketCount] = await Promise.all([
    prisma.collectionRun.findFirst({
      where: { status: 'SUCCESS' },
      orderBy: { finishedAt: 'desc' },
    }),
    prisma.collectionRun.count({ where: { status: 'FAILED' } }),
    prisma.recMarket.count(),
  ])

  return {
    lastSuccessAt: lastSuccess?.finishedAt?.toISOString() ?? null,
    lastSuccessDate: lastSuccess?.targetDate?.toISOString().slice(0, 10) ?? null,
    failureCount,
    marketCount,
  }
}
