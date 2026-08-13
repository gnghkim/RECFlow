'use client'

import { useRouter } from 'next/navigation'
import { useState, type FormEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Field } from '@/app/(app)/inventory/plant-form'

export function TargetForm() {
  const router = useRouter()
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setPending(true)
    setError(null)

    const form = event.currentTarget
    const data = Object.fromEntries(new FormData(form).entries())

    const response = await fetch('/api/targets', {
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

  return (
    <form onSubmit={onSubmit} className="mt-4 space-y-3">
      <Field name="name" label="이름" required />
      <Field name="targetPrice" label="목표가격 (원)" type="number" step="0.01" required />
      {error ? <p className="text-sm text-[var(--color-up)]">{error}</p> : null}
      <Button type="submit" disabled={pending}>
        {pending ? '등록 중…' : '등록'}
      </Button>
    </form>
  )
}
