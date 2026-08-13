import { beforeEach, describe, expect, it, vi } from 'vitest'

const SECRET = 'test-secret-that-is-at-least-32-characters-long'

async function loadAuth() {
  process.env.AUTH_SECRET = SECRET
  const mod = await import('./auth')
  return mod
}

describe('세션 토큰', () => {
  beforeEach(() => {
    process.env.AUTH_SECRET = SECRET
  })

  it('발급한 토큰을 검증한다', async () => {
    const { createSessionToken, verifySessionToken } = await loadAuth()
    const token = await createSessionToken()
    expect(await verifySessionToken(token)).toBe(true)
  })

  it('undefined 토큰을 거부한다', async () => {
    const { verifySessionToken } = await loadAuth()
    expect(await verifySessionToken(undefined)).toBe(false)
  })

  it('빈 문자열을 거부한다', async () => {
    const { verifySessionToken } = await loadAuth()
    expect(await verifySessionToken('')).toBe(false)
  })

  it('변조된 토큰을 거부한다', async () => {
    const { createSessionToken, verifySessionToken } = await loadAuth()
    const token = await createSessionToken()
    const tampered = token.slice(0, -3) + 'aaa'
    expect(await verifySessionToken(tampered)).toBe(false)
  })

  it('다른 키로 서명된 토큰을 거부한다', async () => {
    const { createSessionToken } = await loadAuth()
    const token = await createSessionToken()

    process.env.AUTH_SECRET = 'a-completely-different-secret-key-32chars'
    vi.resetModules()
    const fresh = await import('./auth')
    expect(await fresh.verifySessionToken(token)).toBe(false)
  })
})

describe('비밀번호 검증', () => {
  it('일치하면 true', async () => {
    process.env.APP_PASSWORD = 'correct-horse'
    const { verifyPassword } = await loadAuth()
    expect(verifyPassword('correct-horse')).toBe(true)
  })

  it('불일치하면 false', async () => {
    process.env.APP_PASSWORD = 'correct-horse'
    const { verifyPassword } = await loadAuth()
    expect(verifyPassword('wrong')).toBe(false)
  })

  it('길이가 달라도 예외 없이 false', async () => {
    process.env.APP_PASSWORD = 'correct-horse'
    const { verifyPassword } = await loadAuth()
    expect(verifyPassword('x')).toBe(false)
  })

  it('APP_PASSWORD가 비어 있으면 무엇도 통과시키지 않는다', async () => {
    process.env.APP_PASSWORD = ''
    const { verifyPassword } = await loadAuth()
    expect(verifyPassword('')).toBe(false)
    expect(verifyPassword('anything')).toBe(false)
  })
})
