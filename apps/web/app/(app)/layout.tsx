import { AppNav } from '@/components/app-nav'

// 모든 화면이 DB에서 현재 시세와 보유 현황을 읽는다. Prisma 조회는
// Next의 동적 신호가 아니라서 그냥 두면 빌드 시점 값으로 고정된다.
// 가격추적 시스템에서 낡은 숫자는 화면이 멀쩡해 보이는 만큼 위험하다.
export const dynamic = 'force-dynamic'

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-dvh">
      <AppNav />
      <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
    </div>
  )
}
