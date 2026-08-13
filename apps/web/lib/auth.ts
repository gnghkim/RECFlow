import { timingSafeEqual } from 'node:crypto'
import { SignJWT, jwtVerify } from 'jose'

export const SESSION_COOKIE = 'recflow_session'
const SESSION_MAX_AGE_SECONDS = 60 * 60 * 12 // 12시간

function secretKey(): Uint8Array {
  const secret = process.env.AUTH_SECRET
  if (!secret || secret.length < 32) {
    throw new Error('AUTH_SECRET이 없거나 32자 미만이다. .env를 확인하라.')
  }
  return new TextEncoder().encode(secret)
}

export async function createSessionToken(): Promise<string> {
  return new SignJWT({ scope: 'recflow' })
    .setProtectedHeader({ alg: 'HS256' })
    .setIssuedAt()
    .setExpirationTime(`${SESSION_MAX_AGE_SECONDS}s`)
    .sign(secretKey())
}

export async function verifySessionToken(token: string | undefined | null): Promise<boolean> {
  if (!token) return false
  try {
    await jwtVerify(token, secretKey())
    return true
  } catch {
    return false
  }
}

/**
 * 비밀번호를 상수 시간으로 비교한다.
 * 길이가 다르면 timingSafeEqual이 예외를 던지므로 길이를 먼저 확인하되,
 * 길이 정보만 새는 것은 감수한다. 비밀번호 자체는 유출되지 않는다.
 */
export function verifyPassword(input: string): boolean {
  const expected = process.env.APP_PASSWORD ?? ''
  if (expected.length === 0) return false

  const a = Buffer.from(input, 'utf8')
  const b = Buffer.from(expected, 'utf8')
  if (a.length !== b.length) return false
  return timingSafeEqual(a, b)
}

export const sessionCookieOptions = {
  httpOnly: true,
  sameSite: 'lax' as const,
  secure: process.env.NODE_ENV === 'production',
  path: '/',
  maxAge: SESSION_MAX_AGE_SECONDS,
}
