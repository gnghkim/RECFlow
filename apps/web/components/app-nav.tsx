import Link from 'next/link'

const ITEMS = [
  { href: '/dashboard', label: '대시보드' },
  { href: '/market', label: '시장분석' },
  { href: '/inventory', label: '보유 REC' },
  { href: '/simulation', label: '시뮬레이션' },
  { href: '/settings', label: '목표가격' },
  { href: '/admin', label: '수집 상태' },
]

export function AppNav() {
  return (
    <header className="border-b border-[var(--color-line)]">
      <div className="mx-auto flex max-w-6xl items-center gap-6 px-6 py-3">
        <Link href="/dashboard" className="text-sm font-semibold tracking-tight">
          RECFlow
        </Link>
        <nav className="flex flex-wrap gap-4 text-sm text-[var(--color-muted)]">
          {ITEMS.map((item) => (
            <Link key={item.href} href={item.href} className="hover:text-[var(--color-ink)]">
              {item.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  )
}
