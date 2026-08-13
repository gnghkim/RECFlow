'use client'

import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

export type PriceSeriesPoint = {
  tradeDate: string
  avgPrice: number | null
  ma8?: number | null
  ma26?: number | null
  ma52?: number | null
}

const LINES = [
  { key: 'avgPrice', label: '평균가', color: 'var(--color-ink)', width: 2 },
  { key: 'ma8', label: 'MA8', color: 'var(--color-accent)', width: 1 },
  { key: 'ma26', label: 'MA26', color: 'var(--color-up)', width: 1 },
  { key: 'ma52', label: 'MA52', color: 'var(--color-down)', width: 1 },
] as const

export function PriceChart({ data, height = 320 }: { data: PriceSeriesPoint[]; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
        <CartesianGrid stroke="var(--color-line)" vertical={false} />
        <XAxis
          dataKey="tradeDate"
          tick={{ fontSize: 11, fill: 'var(--color-muted)' }}
          tickLine={false}
          axisLine={false}
          minTickGap={40}
        />
        <YAxis
          tick={{ fontSize: 11, fill: 'var(--color-muted)' }}
          tickLine={false}
          axisLine={false}
          width={64}
          domain={['dataMin - 2000', 'dataMax + 2000']}
          tickFormatter={(value: number) => value.toLocaleString('ko-KR')}
        />
        <Tooltip
          contentStyle={{
            background: 'var(--color-surface)',
            border: '1px solid var(--color-line)',
            borderRadius: 8,
            fontSize: 12,
          }}
          formatter={(value, name) => {
            const numeric = typeof value === 'number' ? value : Number(value)
            return [
              Number.isFinite(numeric) ? `${numeric.toLocaleString('ko-KR')}원` : '—',
              name,
            ]
          }}
        />
        {LINES.map((line) => (
          <Line
            key={line.key}
            type="monotone"
            dataKey={line.key}
            name={line.label}
            stroke={line.color}
            strokeWidth={line.width}
            dot={false}
            // 데이터가 부족해 null인 구간은 선을 잇지 않는다.
            connectNulls={false}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  )
}
