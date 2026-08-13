import { beforeEach, describe, expect, it } from 'vitest'
import { checkRateLimit, resetRateLimit } from './rate-limit'

describe('로그인 시도 제한', () => {
  beforeEach(() => resetRateLimit())

  it('분당 5회까지 허용한다', () => {
    for (let i = 0; i < 5; i++) {
      expect(checkRateLimit('1.2.3.4', 0).allowed).toBe(true)
    }
  })

  it('6회째를 차단한다', () => {
    for (let i = 0; i < 5; i++) checkRateLimit('1.2.3.4', 0)
    const result = checkRateLimit('1.2.3.4', 0)
    expect(result.allowed).toBe(false)
    expect(result.retryAfterSeconds).toBeGreaterThan(0)
  })

  it('키가 다르면 독립적으로 센다', () => {
    for (let i = 0; i < 5; i++) checkRateLimit('1.2.3.4', 0)
    expect(checkRateLimit('5.6.7.8', 0).allowed).toBe(true)
  })

  it('1분이 지나면 창이 초기화된다', () => {
    for (let i = 0; i < 5; i++) checkRateLimit('1.2.3.4', 0)
    expect(checkRateLimit('1.2.3.4', 61_000).allowed).toBe(true)
  })
})
