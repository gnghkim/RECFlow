import { Card, CardTitle } from '@/components/ui/card'
import { Empty } from '@/components/ui/empty'
import { Table, Td, Th } from '@/components/ui/table'
import { Stat } from '@/components/ui/stat'
import { PlantForm } from './plant-form'
import { InventoryForm } from './inventory-form'
import { SaleForm } from './sale-form'
import { prisma } from '@/lib/db'
import { getHoldingsSummary } from '@/lib/queries/company'
import { getLatestMarket } from '@/lib/queries/market'
import { valuation } from '@/lib/analytics/valuation'
import { formatKrw, formatQuantity } from '@/lib/money'

export default async function InventoryPage() {
  const [summary, latest, plants] = await Promise.all([
    getHoldingsSummary(),
    getLatestMarket(),
    prisma.plant.findMany({ orderBy: { name: 'asc' }, select: { id: true, name: true } }),
  ])

  const unitPrice = latest?.avgPrice?.toString() ?? null

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold tracking-tight">보유 REC</h1>

      <Card>
        <div className="grid gap-6 sm:grid-cols-4">
          <Stat label="총 발급" value={formatQuantity(summary.issued)} sub="REC" />
          <Stat label="총 매각" value={formatQuantity(summary.sold)} sub="REC" />
          <Stat label="현재 보유" value={formatQuantity(summary.holdings)} sub="REC" />
          <Stat
            label="현재 평가액"
            value={formatKrw(valuation({ holdings: summary.holdings, unitPrice }).amount, { compact: true })}
            sub={latest ? `${latest.tradeDate} 평균가 기준` : null}
          />
        </div>
      </Card>

      <Card>
        <CardTitle>발전소별</CardTitle>
        {summary.byPlant.length === 0 ? (
          <div className="mt-4">
            <Empty title="등록된 발전소가 없습니다" hint="아래에서 발전소를 먼저 등록하세요." />
          </div>
        ) : (
          <div className="mt-4">
            <Table>
              <thead>
                <tr>
                  <Th>발전소</Th>
                  <Th align="right">발급</Th>
                  <Th align="right">매각</Th>
                  <Th align="right">보유</Th>
                  <Th align="right">평가액</Th>
                </tr>
              </thead>
              <tbody>
                {summary.byPlant.map((plant) => (
                  <tr key={plant.plantId}>
                    <Td>{plant.plantName}</Td>
                    <Td align="right">{formatQuantity(plant.issued)}</Td>
                    <Td align="right">{formatQuantity(plant.sold)}</Td>
                    <Td align="right">{formatQuantity(plant.holdings)}</Td>
                    <Td align="right">
                      {formatKrw(valuation({ holdings: plant.holdings, unitPrice }).amount, { compact: true })}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>
        )}
      </Card>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card>
          <CardTitle>발전소 등록</CardTitle>
          <PlantForm />
        </Card>
        <Card>
          <CardTitle>REC 발급 등록</CardTitle>
          <InventoryForm plants={plants} />
        </Card>
        <Card>
          <CardTitle>매각 등록</CardTitle>
          <SaleForm plants={plants} />
        </Card>
      </div>
    </div>
  )
}
