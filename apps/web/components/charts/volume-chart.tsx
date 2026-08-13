'use client'

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

export function VolumeChart({
  data,
  height = 200,
}: {
  data: { tradeDate: string; volume: number | null }[]
  height?: number
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
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
          tickFormatter={(value: number) => value.toLocaleString('ko-KR')}
        />
        <Tooltip
          contentStyle={{
            background: 'var(--color-surface)',
            border: '1px solid var(--color-line)',
            borderRadius: 8,
            fontSize: 12,
          }}
          formatter={(value) => {
            const numeric = typeof value === 'number' ? value : Number(value)
            return [
              Number.isFinite(numeric) ? `${numeric.toLocaleString('ko-KR')} REC` : '—',
              '거래량',
            ]
          }}
        />
        <Bar dataKey="volume" fill="var(--color-accent)" isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  )
}
