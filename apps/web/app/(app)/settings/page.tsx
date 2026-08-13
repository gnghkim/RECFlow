import Decimal from 'decimal.js'
import { Card, CardTitle } from '@/components/ui/card'
import { Empty } from '@/components/ui/empty'
import { Badge } from '@/components/ui/badge'
import { Table, Td, Th } from '@/components/ui/table'
import { TargetForm } from './target-form'
import { prisma } from '@/lib/db'
import { getLatestMarket } from '@/lib/queries/market'
import { DASH, formatKrw } from '@/lib/money'

export default async function SettingsPage() {
  const [targets, latest] = await Promise.all([
    prisma.priceTarget.findMany({ orderBy: { targetPrice: 'asc' } }),
    getLatestMarket(),
  ])

  const current = latest?.avgPrice ?? null

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">목표가격</h1>
        <p className="mt-1 text-sm text-[var(--color-muted)]">
          {current === null ? '현재가 없음' : `현재가 ${formatKrw(current)}`}
        </p>
      </div>

      <Card>
        <CardTitle>등록된 목표가격</CardTitle>
        {targets.length === 0 ? (
          <div className="mt-4">
            <Empty
              title="설정된 목표가격이 없습니다"
              hint="매각을 검토할 가격을 등록하면 대시보드와 시뮬레이션에서 기준으로 쓰입니다."
            />
          </div>
        ) : (
          <div className="mt-4">
            <Table>
              <thead>
                <tr>
                  <Th>이름</Th>
                  <Th align="right">목표가격</Th>
                  <Th align="right">현재가 대비</Th>
                  <Th align="right">상태</Th>
                </tr>
              </thead>
              <tbody>
                {targets.map((target) => {
                  const price = new Decimal(target.targetPrice.toString())
                  const reached = current !== null && new Decimal(current).gte(price)
                  const remaining =
                    current === null ? null : price.minus(new Decimal(current)).toString()

                  return (
                    <tr key={target.id}>
                      <Td>{target.name}</Td>
                      <Td align="right">{formatKrw(price.toString())}</Td>
                      <Td align="right">
                        {remaining === null ? DASH : reached ? '달성' : `${formatKrw(remaining)} 남음`}
                      </Td>
                      <Td align="right">
                        <Badge tone={reached ? 'up' : 'neutral'}>
                          {!target.isActive ? '비활성' : reached ? '도달' : '대기'}
                        </Badge>
                      </Td>
                    </tr>
                  )
                })}
              </tbody>
            </Table>
          </div>
        )}
      </Card>

      <Card>
        <CardTitle>목표가격 등록</CardTitle>
        <TargetForm />
      </Card>
    </div>
  )
}
