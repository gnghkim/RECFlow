export function Empty({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-dashed border-[var(--color-line)] p-10 text-center">
      <p className="text-sm font-medium">{title}</p>
      {hint ? <p className="mt-1 text-sm text-[var(--color-muted)]">{hint}</p> : null}
    </div>
  )
}
