'use client'

import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { Button } from '@/components/ui/button'

export function CollectButton() {
  const router = useRouter()
  const [tradeDate, setTradeDate] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  async function run() {
    setPending(true)
    setMessage(null)

    const response = await fetch('/api/admin/collect', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ tradeDate }),
    })
    const payload = (await response.json().catch(() => ({}))) as Record<string, unknown>

    setMessage(
      response.ok
        ? `${payload.status} · ${payload.rowsUpserted}행 적재`
        : String(payload.error ?? '수집에 실패했습니다.'),
    )
    setPending(false)
    if (response.ok) router.refresh()
  }

  return (
    <div className="mt-4 flex flex-wrap items-end gap-2">
      <label className="text-sm">
        <span className="text-[var(--color-muted)]">거래일</span>
        <input
          type="date"
          value={tradeDate}
          onChange={(event) => setTradeDate(event.target.value)}
          className="mt-1 block rounded-md border border-[var(--color-line)] bg-[var(--color-canvas)] px-2.5 py-1.5 text-sm outline-none focus:border-[var(--color-accent)]"
        />
      </label>
      <Button type="button" onClick={run} disabled={pending || tradeDate === ''}>
        {pending ? '수집 중…' : '수집 실행'}
      </Button>
      {message ? <span className="text-sm text-[var(--color-muted)]">{message}</span> : null}
    </div>
  )
}
