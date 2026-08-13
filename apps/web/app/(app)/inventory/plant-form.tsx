'use client'

import { useRouter } from 'next/navigation'
import { useState, type FormEvent } from 'react'
import { Button } from '@/components/ui/button'

export function PlantForm() {
  const router = useRouter()
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setPending(true)
    setError(null)

    const form = event.currentTarget
    const data = Object.fromEntries(new FormData(form).entries())

    const response = await fetch('/api/plants', {
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
      <Field name="name" label="발전소명" required />
      <Field name="location" label="위치" />
      <Field name="capacityKw" label="설비용량 (kW)" type="number" step="0.01" />
      <Field name="recWeight" label="REC 가중치 (참고용)" type="number" step="0.01" />
      {error ? <p className="text-sm text-[var(--color-up)]">{error}</p> : null}
      <Button type="submit" disabled={pending}>
        {pending ? '등록 중…' : '등록'}
      </Button>
    </form>
  )
}

export function Field({
  name,
  label,
  type = 'text',
  required = false,
  step,
  options,
}: {
  name: string
  label: string
  type?: string
  required?: boolean
  step?: string
  options?: { value: string | number; label: string }[]
}) {
  const className =
    'mt-1 w-full rounded-md border border-[var(--color-line)] bg-[var(--color-canvas)] px-2.5 py-1.5 text-sm outline-none focus:border-[var(--color-accent)]'

  return (
    <label className="block text-sm">
      <span className="text-[var(--color-muted)]">{label}</span>
      {options ? (
        <select name={name} required={required} className={className}>
          <option value="">선택하세요</option>
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      ) : (
        <input name={name} type={type} step={step} required={required} className={className} />
      )}
    </label>
  )
}
