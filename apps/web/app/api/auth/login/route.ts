import { cookies, headers } from 'next/headers'
import { NextResponse } from 'next/server'
import { SESSION_COOKIE, createSessionToken, sessionCookieOptions, verifyPassword } from '@/lib/auth'
import { checkRateLimit } from '@/lib/rate-limit'

export async function POST(request: Request) {
  const headerList = await headers()
  const clientKey = headerList.get('x-forwarded-for')?.split(',')[0]?.trim() ?? 'unknown'

  const limit = checkRateLimit(clientKey)
  if (!limit.allowed) {
    return NextResponse.json(
      { error: `시도가 너무 많다. ${limit.retryAfterSeconds}초 후 다시 시도하라.` },
      { status: 429 },
    )
  }

  const body = (await request.json().catch(() => null)) as { password?: string } | null
  if (!body || typeof body.password !== 'string') {
    return NextResponse.json({ error: '비밀번호가 필요하다' }, { status: 400 })
  }

  if (!verifyPassword(body.password)) {
    // 실패 사유를 세분화하지 않는다. 공격자에게 정보를 주지 않는다.
    return NextResponse.json({ error: '비밀번호가 올바르지 않다' }, { status: 401 })
  }

  const cookieStore = await cookies()
  cookieStore.set(SESSION_COOKIE, await createSessionToken(), sessionCookieOptions)
  return NextResponse.json({ ok: true })
}
