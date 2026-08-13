'use client'

import { useRouter } from 'next/navigation'
import { useState, type FormEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Field } from './plant-form'

export function SaleForm({ plants }: { plants: { id: number; name: string }[] }) {
  const router = useRouter()
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setPending(true)
    setError(null)

    const form = event.currentTarget
    const data = Object.fromEntries(new FormData(form).entries())

    const response = await fetch('/api/sales', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(data),
    })

    if (response.ok) {
      form.reset()
      router.refresh()
    } else {
      const payload = (await response.json().catch(() => ({}))) as { error?: string }
      setError(payload.error ?? '등록에 실패했습니다.')
    }
    setPending(false)
  }

  if (plants.length === 0) {
    return <p className="mt-4 text-sm text-[var(--color-muted)]">발전소를 먼저 등록하세요.</p>
  }

  return (
    <form onSubmit={onSubmit} className="mt-4 space-y-3">
      <Field
        name="plantId"
        label="발전소"
        required
        options={plants.map((plant) => ({ value: plant.id, label: plant.name }))}
      />
      <Field name="saleDate" label="매각일" type="date" required />
      <Field name="quantity" label="매각 수량" type="number" step="0.01" required />
      <Field name="unitPrice" label="단가 (원)" type="number" step="0.01" required />
      <Field name="buyer" label="매수자" />
      {error ? <p className="text-sm text-[var(--color-up)]">{error}</p> : null}
      <Button type="submit" disabled={pending}>
        {pending ? '등록 중…' : '등록'}
      </Button>
    </form>
  )
}
