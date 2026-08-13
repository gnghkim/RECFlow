export function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <div
      className={`rounded-lg border border-[var(--color-line)] bg-[var(--color-surface)] p-5 ${className}`}
    >
      {children}
    </div>
  )
}

export function CardTitle({ children }: { children: React.ReactNode }) {
  return <h2 className="text-sm font-medium text-[var(--color-muted)]">{children}</h2>
}
