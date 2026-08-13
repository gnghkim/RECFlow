/**
 * 단일 인스턴스 인메모리 카운터. 사내 소수 사용자를 전제로 한다.
 * 프로세스가 재시작되면 초기화되지만, 무차별 대입을 늦추는 목적에는 충분하다.
 */
const WINDOW_MS = 60_000
const MAX_ATTEMPTS = 5

type Entry = { count: number; windowStart: number }
const attempts = new Map<string, Entry>()

export function resetRateLimit(): void {
  attempts.clear()
}

export function checkRateLimit(
  key: string,
  now: number = Date.now(),
): { allowed: boolean; retryAfterSeconds: number } {
  const entry = attempts.get(key)

  if (!entry || now - entry.windowStart >= WINDOW_MS) {
    attempts.set(key, { count: 1, windowStart: now })
    return { allowed: true, retryAfterSeconds: 0 }
  }

  if (entry.count >= MAX_ATTEMPTS) {
    const retryAfterSeconds = Math.ceil((entry.windowStart + WINDOW_MS - now) / 1000)
    return { allowed: false, retryAfterSeconds: Math.max(1, retryAfterSeconds) }
  }

  entry.count += 1
  return { allowed: true, retryAfterSeconds: 0 }
}
