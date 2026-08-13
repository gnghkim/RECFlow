'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Table, Td, Th } from '@/components/ui/table'
import { DASH, formatKrw, formatQuantity } from '@/lib/money'

type SimulationRow = { price: string; revenue: string; deltaFromCurrent: string | null }
type TrancheResult = {
  totalQuantity: string
  totalRevenue: string
  averagePrice: string | null
  rows: { quantity: string; price: string; revenue: string }[]
}

/** 현재가 기준 ±5%를 5단계로 나눈 기본 제안값. 현재가가 없으면 빈 값이다. */
function defaultPrices(currentPrice: string | null): string {
  if (currentPrice === null) return ''
  const base = Number(currentPrice)
  if (!Number.isFinite(base)) return ''
  return [-0.05, -0.025, 0, 0.025, 0.05]
    .map((ratio) => Math.round((base * (1 + ratio)) / 100) * 100)
    .join(', ')
}

export function SimulationPanel({
  holdings,
  currentPrice,
}: {
  holdings: string
  currentPrice: string | null
}) {
  const [mode, setMode] = useState<'full' | 'tranches'>('full')
  const [quantity, setQuantity] = useState(holdings)
  const [priceText, setPriceText] = useState(defaultPrices(currentPrice))
  const [rows, setRows] = useState<SimulationRow[] | null>(null)

  const [tranches, setTranches] = useState([
    { quantity: '', price: '' },
    { quantity: '', price: '' },
  ])
  const [trancheResult, setTrancheResult] = useState<TrancheResult | null>(null)

  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  async function post(body: unknown) {
    setPending(true)
    setError(null)
    const response = await fetch('/api/simulation', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    })
    const payload = await response.json().catch(() => ({}))
    setPending(false)
    if (!response.ok) {
      setError((payload as { error?: string }).error ?? '계산에 실패했습니다.')
      return null
    }
    return payload
  }

  async function runFull() {
    const prices = priceText
      .split(',')
      .map((value) => value.trim())
      .filter((value) => value.length > 0)
    const result = await post({ quantity, prices, currentPrice })
    if (result) setRows((result as { rows: SimulationRow[] }).rows)
  }

  async function runTranches() {
    const result = await post({ mode: 'tranches', tranches })
    if (result) setTrancheResult(result as TrancheResult)
  }

  const trancheTotal = tranches.reduce((sum, row) => sum + (Number(row.quantity) || 0), 0)
  const overHoldings = trancheTotal > Number(holdings)

  const inputClass =
    'w-full rounded-md border border-[var(--color-line)] bg-[var(--color-canvas)] px-2.5 py-1.5 text-sm tabular outline-none focus:border-[var(--color-accent)]'

  return (
    <div>
      <div className="flex gap-1">
        {(['full', 'tranches'] as const).map((key) => (
          <button
            key={key}
            type="button"
            onClick={() => setMode(key)}
            className={`rounded-md px-3 py-1.5 text-sm ${
              mode === key
                ? 'bg-[var(--color-accent)] text-white'
                : 'border border-[var(--color-line)] text-[var(--color-muted)]'
            }`}
          >
            {key === 'full' ? '전량 매각' : '분할 매각'}
          </button>
        ))}
      </div>

      {error ? <p className="mt-4 text-sm text-[var(--color-up)]">{error}</p> : null}

      {mode === 'full' ? (
        <div className="mt-5 space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block text-sm">
              <span className="text-[var(--color-muted)]">매각 수량 (REC)</span>
              <input
                value={quantity}
                onChange={(event) => setQuantity(event.target.value)}
                className={`mt-1 ${inputClass}`}
              />
            </label>
            <label className="block text-sm">
              <span className="text-[var(--color-muted)]">검토 가격 (쉼표로 구분)</span>
              <input
                value={priceText}
                onChange={(event) => setPriceText(event.target.value)}
                className={`mt-1 ${inputClass}`}
              />
            </label>
          </div>

          <Button type="button" onClick={runFull} disabled={pending}>
            {pending ? '계산 중…' : '계산'}
          </Button>

          {rows ? (
            <Table>
              <thead>
                <tr>
                  <Th align="right">가격</Th>
                  <Th align="right">예상 매출</Th>
                  <Th align="right">현재가 대비</Th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const delta = row.deltaFromCurrent
                  const tone =
                    delta === null
                      ? ''
                      : delta.startsWith('-')
                        ? 'text-[var(--color-down)]'
                        : 'text-[var(--color-up)]'
                  return (
                    <tr key={row.price}>
                      <Td align="right">{formatKrw(row.price)}</Td>
                      <Td align="right">{formatKrw(row.revenue)}</Td>
                      <Td align="right">
                        <span className={tone}>
                          {delta === null ? DASH : formatKrw(delta)}
                        </span>
                      </Td>
                    </tr>
                  )
                })}
              </tbody>
            </Table>
          ) : null}
        </div>
      ) : (
        <div className="mt-5 space-y-4">
          <div className="space-y-2">
            {tranches.map((tranche, index) => (
              <div key={index} className="flex items-end gap-2">
                <label className="flex-1 text-sm">
                  <span className="text-[var(--color-muted)]">{index + 1}차 수량</span>
                  <input
                    value={tranche.quantity}
                    onChange={(event) =>
                      setTranches((prev) =>
                        prev.map((row, i) => (i === index ? { ...row, quantity: event.target.value } : row)),
                      )
                    }
                    className={`mt-1 ${inputClass}`}
                  />
                </label>
                <label className="flex-1 text-sm">
                  <span className="text-[var(--color-muted)]">{index + 1}차 가격</span>
                  <input
                    value={tranche.price}
                    onChange={(event) =>
                      setTranches((prev) =>
                        prev.map((row, i) => (i === index ? { ...row, price: event.target.value } : row)),
                      )
                    }
                    className={`mt-1 ${inputClass}`}
                  />
                </label>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setTranches((prev) => prev.filter((_, i) => i !== index))}
                  disabled={tranches.length <= 1}
                >
                  삭제
                </Button>
              </div>
            ))}
          </div>

          <div className="flex gap-2">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setTranches((prev) => [...prev, { quantity: '', price: '' }])}
            >
              회차 추가
            </Button>
            <Button type="button" onClick={runTranches} disabled={pending}>
              {pending ? '계산 중…' : '계산'}
            </Button>
          </div>

          {overHoldings ? (
            <p className="text-sm text-[var(--color-up)]">
              회차 수량 합계 {formatQuantity(trancheTotal)} REC가 보유량 {formatQuantity(holdings)} REC를
              넘습니다. 계획 단계이므로 계산은 가능합니다.
            </p>
          ) : null}

          {trancheResult ? (
            <div className="space-y-4">
              <Table>
                <thead>
                  <tr>
                    <Th>회차</Th>
                    <Th align="right">수량</Th>
                    <Th align="right">가격</Th>
                    <Th align="right">매출</Th>
                  </tr>
                </thead>
                <tbody>
                  {trancheResult.rows.map((row, index) => (
                    <tr key={index}>
                      <Td>{index + 1}차</Td>
                      <Td align="right">{formatQuantity(row.quantity)}</Td>
                      <Td align="right">{formatKrw(row.price)}</Td>
                      <Td align="right">{formatKrw(row.revenue)}</Td>
                    </tr>
                  ))}
                </tbody>
              </Table>

              <div className="grid gap-6 sm:grid-cols-3 border-t border-[var(--color-line)] pt-4">
                <div>
                  <p className="text-sm text-[var(--color-muted)]">총 매각량</p>
                  <p className="tabular mt-1 text-xl font-semibold">
                    {formatQuantity(trancheResult.totalQuantity)} REC
                  </p>
                </div>
                <div>
                  <p className="text-sm text-[var(--color-muted)]">총 예상매출</p>
                  <p className="tabular mt-1 text-xl font-semibold">
                    {formatKrw(trancheResult.totalRevenue)}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-[var(--color-muted)]">평균 매도가 (가중)</p>
                  <p className="tabular mt-1 text-xl font-semibold">
                    {formatKrw(trancheResult.averagePrice)}
                  </p>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      )}
    </div>
  )
}
