import { LoginForm } from './login-form'

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string }>
}) {
  const { next } = await searchParams
  return (
    <main className="grid min-h-dvh place-items-center px-6">
      <div className="w-full max-w-sm">
        <h1 className="text-2xl font-semibold tracking-tight">RECFlow</h1>
        <p className="mt-1 text-sm text-[var(--color-muted)]">태양광 REC 가격추적 시스템</p>
        <LoginForm nextPath={next ?? '/dashboard'} />
      </div>
    </main>
  )
}
