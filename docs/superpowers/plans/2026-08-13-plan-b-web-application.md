# 계획 B — 웹 애플리케이션 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 계획 A가 축적한 REC 시세를 읽어 대시보드·시장분석·보유REC·매각 시뮬레이션·매각 판단 지표를 제공하는 사내 웹 애플리케이션을 만든다.

**Architecture:** Next.js App Router. 조회는 Server Component에서 Prisma로 직접 수행하고, 클라이언트 상호작용(기간 변경·CRUD·시뮬레이션)만 Route Handler를 쓴다. 이동평균·백분위·매각점수·시뮬레이션은 DB와 React를 모르는 순수 함수로 `lib/analytics/`에 격리하고 Vitest로 TDD한다. 인증은 단일 비밀번호 + 서명 쿠키이며 사용자 테이블이 없다.

**Tech Stack:** Next.js 16.3, React 19.2, TypeScript 5, Tailwind CSS 4, Recharts 3, Prisma 6.19, decimal.js 10, jose 6, Vitest 4

**설계문서:** `docs/superpowers/specs/2026-08-12-rec-price-tracker-design.md` — 충돌 시 설계문서가 우선한다.
**선행 계획:** `docs/superpowers/plans/2026-08-12-plan-a-data-pipeline.md` (완료)

---

## Global Constraints

- 작업 디렉토리는 `C:\Dev\RECFlow`. git 저장소이며 브랜치는 `main`, 원격은 `origin`.
- 개발 호스트는 **Windows 11 + PowerShell**. `&&`는 파서 오류를 내므로 `;`와 `if ($?) { }`를 쓴다.
- **웹은 호스트에서 직접 실행한다** (Node 24.14 설치됨). 계획 A의 파이썬과 달리 컨테이너에 넣지 않는다. DB는 `docker compose up -d db`로 띄운 컨테이너를 `localhost:5432`로 접속한다.
- **버전은 아래로 고정한다.** 이 값들은 2026-08-13 기준 실제 확인값이다.

  | 패키지 | 버전 |
  |---|---|
  | `next` | `16.3.0` |
  | `react` / `react-dom` | `19.2.8` |
  | `tailwindcss` / `@tailwindcss/postcss` | `4.3.3` |
  | `recharts` | `3.10.1` |
  | `jose` | `6.2.8` |
  | `decimal.js` | `10.6.0` |
  | `vitest` | `4.1.10` |
  | `prisma` / `@prisma/client` | `6.19.3` (이미 설치됨, **올리지 말 것**) |

- **Next.js 16 규약을 반드시 지킬 것** (15와 다르다):
  - `middleware.ts`가 아니라 **`proxy.ts`**이고, export 이름은 `middleware`가 아니라 **`proxy`**다.
  - `proxy`는 **Node.js 런타임**에서 돈다. Edge가 아니다. 런타임은 설정할 수 없다.
  - `cookies()`, `headers()`, `params`, `searchParams`는 **전부 async**다. 반드시 `await` 한다.
- **Prisma 스키마는 계획 A가 소유한다.** 이번 계획에서 `prisma/schema.prisma`를 수정하지 않는다. 새 테이블이 필요하다고 판단되면 진행하지 말고 `orca orchestration ask`로 물어라.
- **금액과 지표의 타입 규칙** (아래 "타입 경계" 절 참조):
  - 통계 지표(이동평균·백분위·점수)는 `number`로 계산한다.
  - 금액(평가액·매출·시뮬레이션)은 `Decimal`로 계산하고 **문자열로** 화면에 전달한다.
  - Prisma의 `Decimal`을 Server Component에서 Client Component로 그대로 넘기지 않는다. 직렬화되지 않는다.
- **계산 불가는 `null`이다.** 데이터가 부족하면 0이나 직전값으로 채우지 않는다. 화면은 `—`로 표시한다. 이 규칙을 어기면 매각 판단 지표가 조용히 틀린 값을 낸다.
- 비밀값은 `.env`로만 관리한다. `.env`를 커밋하지 않는다.
- 각 Task는 마지막에 커밋으로 끝난다. Conventional Commits 접두사 + 한국어 본문.
- 이번 계획에서 **SMP, Telegram 알림, 배포(Caddy/운영 compose/백업)는 만들지 않는다.**

### 계획 A에서 이어지는 사실

- DB `recflow`에 `rec_market` 939행(거래일 313일 × `LAND`/`JEJU`/`TOTAL`)이 `source='fixture'`로 적재되어 있다. 기간은 2023-08-15 ~ 2026-08-11.
- `close_price`와 `trade_amount`는 **`TOTAL` 행에만** 채워져 있다. `LAND`/`JEJU`는 `NULL`이다.
- 회사 데이터 테이블(`plants`, `rec_inventory`, `rec_sales`, `price_targets`)은 **비어 있다.**
- 수집기 컨테이너는 내부 전용 `GET /health`, `POST /jobs/collect`를 `http://collector:8000`에 제공한다. 호스트 포트는 열려 있지 않다.

### 타입 경계 (전 Task 공통)

Prisma는 `numeric` 컬럼을 `Decimal` 객체로 돌려준다. 이 객체는 JSON 직렬화도, Server → Client 전달도 되지 않는다. 경계를 한 곳에 모은다.

```text
PostgreSQL numeric
      │
      ▼  Prisma
   Decimal  ────────────── lib/queries/*.ts 에서 변환 ─────────────▶  MarketPoint (평범한 객체)
      │                                                                  │
      │ 금액 계산은 Decimal 유지                                          │ number | string | null
      ▼                                                                  ▼
 lib/analytics/valuation.ts, simulation.ts  ──▶ 문자열      Client Component / Recharts
```

- `lib/queries/`가 유일한 변환 지점이다. 다른 곳에서 `Decimal`을 만지지 않는다.
- 차트 좌표와 통계는 `number`. 원 단위 가격은 최대 6자리라 배정밀도로 정확히 표현된다.
- 합계 금액(억 단위)은 `Decimal`로 계산하고 문자열로 넘긴다.

---

## File Structure

| 파일 | 책임 |
|---|---|
| `apps/web/lib/db.ts` | PrismaClient 싱글턴 |
| `apps/web/lib/money.ts` | Decimal 헬퍼와 원화 포맷 |
| `apps/web/lib/types.ts` | `MarketPoint` 등 직렬화된 도메인 타입 |
| `apps/web/lib/queries/market.ts` | 시세 조회 + Decimal → 평범한 객체 변환 |
| `apps/web/lib/queries/company.ts` | 발전소·발급·매각·목표가 조회 및 집계 |
| `apps/web/lib/analytics/ma.ts` | 이동평균 |
| `apps/web/lib/analytics/percentile.ts` | 백분위와 가격 위치 구간 |
| `apps/web/lib/analytics/valuation.ts` | 평가액 |
| `apps/web/lib/analytics/simulation.ts` | 목표가별·분할 매각 시뮬레이션 |
| `apps/web/lib/analytics/score.ts` | 매각 판단 점수 |
| `apps/web/lib/auth.ts` | 세션 서명·검증 |
| `apps/web/proxy.ts` | 인증 게이트 (Next 16 규약) |
| `apps/web/components/ui/*` | Button, Card, Table, Input, Field, Stat, Empty |
| `apps/web/components/charts/*` | Recharts 래퍼 (`'use client'`) |
| `apps/web/app/(app)/*` | 화면 |
| `apps/web/app/api/*` | Route Handler |

---

### Task 1: Next.js 앱 스캐폴드

**Files:**
- Modify: `package.json` (workspaces 추가)
- Create: `apps/web/package.json`, `apps/web/tsconfig.json`, `apps/web/next.config.ts`
- Create: `apps/web/postcss.config.mjs`, `apps/web/app/globals.css`
- Create: `apps/web/app/layout.tsx`, `apps/web/app/page.tsx`
- Create: `apps/web/lib/db.ts`
- Create: `apps/web/vitest.config.ts`
- Modify: `.env.example`, `.gitignore`

**Interfaces:**
- Consumes: 계획 A의 `prisma/schema.prisma`, `DATABASE_URL`
- Produces: `prisma` 싱글턴 (`import { prisma } from '@/lib/db'`), 동작하는 `npm run dev` / `npm run build` / `npm run test`

- [ ] **Step 1: 루트 `package.json`에 workspaces와 스크립트 추가**

기존 `scripts`와 `devDependencies`는 그대로 두고 아래를 반영한다.

```json
{
  "name": "recflow",
  "private": true,
  "version": "0.1.0",
  "workspaces": ["apps/web"],
  "scripts": {
    "db:migrate": "prisma migrate dev --schema prisma/schema.prisma",
    "db:deploy": "prisma migrate deploy --schema prisma/schema.prisma",
    "db:generate": "prisma generate --schema prisma/schema.prisma",
    "db:studio": "prisma studio --schema prisma/schema.prisma",
    "dev": "npm run dev --workspace apps/web",
    "build": "npm run build --workspace apps/web",
    "test": "npm run test --workspace apps/web"
  },
  "devDependencies": {
    "prisma": "^6.1.0"
  },
  "dependencies": {
    "@prisma/client": "^6.1.0"
  }
}
```

- [ ] **Step 2: `apps/web/package.json` 작성**

```json
{
  "name": "@recflow/web",
  "private": true,
  "version": "0.1.0",
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "test": "vitest run",
    "test:watch": "vitest",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "@prisma/client": "6.19.3",
    "decimal.js": "10.6.0",
    "jose": "6.2.8",
    "next": "16.3.0",
    "react": "19.2.8",
    "react-dom": "19.2.8",
    "recharts": "3.10.1"
  },
  "devDependencies": {
    "@tailwindcss/postcss": "4.3.3",
    "@types/node": "24.10.1",
    "@types/react": "19.2.8",
    "@types/react-dom": "19.2.8",
    "postcss": "8.5.6",
    "tailwindcss": "4.3.3",
    "typescript": "5.9.3",
    "vitest": "4.1.10"
  }
}
```

`@types/node`, `postcss`, `typescript` 버전은 설치 시 해당 major에서 최신으로 해석되면 그대로 둔다. 설치가 실패하면 정확한 버전을 `npm view <pkg> version`으로 확인해 맞춘다.

- [ ] **Step 3: TypeScript 설정**

> **Next는 빌드할 때 이 파일의 일부 필드를 스스로 관리한다.** `jsx` 값과 `include`의 생성 타입 경로가 그렇다. 첫 `npm run build` 후 아래 내용과 달라져 있어도 **되돌리지 말고 그대로 커밋한다.** 되돌리면 다음 빌드가 다시 바꾸므로 무한 반복이 된다.

`apps/web/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": false,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 4: Next 설정과 Tailwind 4 설정**

`apps/web/next.config.ts`:

```ts
import { existsSync } from 'node:fs'
import path from 'node:path'
import type { NextConfig } from 'next'

// Next는 자신의 프로젝트 루트(apps/web)에서만 .env를 찾는다. 이 저장소는
// 루트 .env가 단일 진실 원천이고 Prisma CLI와 collector compose도 같은
// 파일을 쓰므로, 비밀값을 복제하지 않고 여기서 명시적으로 읽는다.
// next.config.ts는 서버 기동 전에 평가되므로 Route Handler, Server
// Component, proxy 모두 process.env를 볼 수 있다.
const rootEnv = path.resolve(process.cwd(), '../../.env')
if (existsSync(rootEnv)) {
  process.loadEnvFile(rootEnv)
}

const nextConfig: NextConfig = {
  output: 'standalone',
  // 계획 C의 Docker 이미지를 위해 리포 루트를 추적 기준으로 삼는다.
  outputFileTracingRoot: path.resolve(process.cwd(), '../..'),
}

export default nextConfig
```

`process.loadEnvFile`은 Node 20.12+ 내장이므로 `dotenv` 의존성이 필요 없다.

`apps/web/postcss.config.mjs` — Tailwind 4는 별도 PostCSS 플러그인 패키지를 쓴다. v3의 `tailwind.config.js`는 만들지 않는다.

```js
const config = {
  plugins: {
    '@tailwindcss/postcss': {},
  },
}

export default config
```

- [ ] **Step 5: 전역 스타일**

`apps/web/app/globals.css` — Tailwind 4는 `@tailwind` 지시어가 아니라 `@import`를 쓴다.

```css
@import "tailwindcss";

@theme {
  --font-sans: ui-sans-serif, system-ui, "Pretendard", "Malgun Gothic", sans-serif;
  --font-mono: ui-monospace, "Cascadia Mono", "Consolas", monospace;

  --color-canvas: oklch(0.99 0.002 250);
  --color-surface: oklch(1 0 0);
  --color-line: oklch(0.91 0.004 250);
  --color-ink: oklch(0.22 0.01 250);
  --color-muted: oklch(0.52 0.012 250);
  --color-accent: oklch(0.55 0.14 250);
  --color-up: oklch(0.55 0.16 25);
  --color-down: oklch(0.52 0.13 245);
}

@media (prefers-color-scheme: dark) {
  @theme {
    --color-canvas: oklch(0.18 0.008 250);
    --color-surface: oklch(0.22 0.009 250);
    --color-line: oklch(0.31 0.01 250);
    --color-ink: oklch(0.95 0.004 250);
    --color-muted: oklch(0.68 0.012 250);
  }
}

html, body {
  background: var(--color-canvas);
  color: var(--color-ink);
}

/* 시세 표는 자릿수가 흔들리면 읽기 어렵다. 숫자는 항상 고정폭으로 정렬한다. */
.tabular {
  font-variant-numeric: tabular-nums;
  font-feature-settings: "tnum";
}
```

한국 시장 관행에 따라 **상승이 빨강(`--color-up`), 하락이 파랑(`--color-down`)** 이다. 미국식과 반대이므로 임의로 바꾸지 말 것.

- [ ] **Step 6: 루트 레이아웃과 임시 홈**

`apps/web/app/layout.tsx`:

```tsx
import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'RECFlow',
  description: '태양광 REC 가격추적 시스템',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body className="min-h-dvh antialiased">{children}</body>
    </html>
  )
}
```

`apps/web/app/page.tsx` — Task 7에서 대시보드로 리다이렉트하도록 바꾼다.

```tsx
export default function Home() {
  return <main className="p-8">RECFlow</main>
}
```

- [ ] **Step 7: Prisma 클라이언트 싱글턴**

`apps/web/lib/db.ts` — 개발 중 HMR이 연결을 계속 새로 만들어 커넥션을 소진하는 것을 막는다.

```ts
import { PrismaClient } from '@prisma/client'

const globalForPrisma = globalThis as unknown as { prisma?: PrismaClient }

export const prisma =
  globalForPrisma.prisma ??
  new PrismaClient({
    log: process.env.NODE_ENV === 'development' ? ['warn', 'error'] : ['error'],
  })

if (process.env.NODE_ENV !== 'production') globalForPrisma.prisma = prisma
```

- [ ] **Step 8: Vitest 설정**

`apps/web/vitest.config.ts` — `lib/` 아래 순수 함수만 대상으로 한다. 컴포넌트 테스트는 이번 범위가 아니다.

```ts
import { defineConfig } from 'vitest/config'
import path from 'node:path'

export default defineConfig({
  test: {
    include: ['lib/**/*.test.ts'],
    environment: 'node',
  },
  resolve: {
    alias: { '@': path.resolve(__dirname, '.') },
  },
})
```

- [ ] **Step 9: 환경변수와 gitignore 갱신**

`.env.example`에 아래를 덧붙인다.

```text
# --- Web ---
# 사내 로그인 비밀번호. 사용자 계정은 없다.
APP_PASSWORD=change-me-in-real-env
# 세션 쿠키 서명 키. openssl rand -base64 32 등으로 생성한다.
AUTH_SECRET=change-me-at-least-32-characters-long
# 수집기 내부 API. Docker 내부 네트워크 전용이며 외부에 노출하지 않는다.
COLLECTOR_INTERNAL_URL=http://collector:8000
```

`.gitignore`에 아래를 덧붙인다.

```text
# Next.js
apps/web/.next/
apps/web/next-env.d.ts
apps/web/.vercel/
```

로컬 `.env`에도 `APP_PASSWORD`와 `AUTH_SECRET`을 실제 값으로 채운다. `AUTH_SECRET`은 32자 이상이어야 한다.

- [ ] **Step 10: 설치와 기동 확인**

```powershell
cd C:\Dev\RECFlow
npm install
npm run db:generate
npm run build
```

Expected: 빌드가 성공한다. 실패하면 원인을 해결한 뒤 진행한다.

```powershell
npm run dev
```

Expected: `http://localhost:3000`에서 `RECFlow`가 보인다. 확인 후 종료한다.

- [ ] **Step 11: 커밋**

```powershell
cd C:\Dev\RECFlow
git add -A
git commit -m "feat(web): Next.js 16 앱 스캐폴드

npm workspaces에 apps/web을 추가하고 Tailwind 4, Prisma 클라이언트
싱글턴, Vitest를 구성했다.

Tailwind 4는 tailwind.config.js가 아니라 CSS의 @import와
@tailwindcss/postcss 플러그인으로 설정한다. 상승 빨강 하락 파랑은
한국 시장 관행이며 임의로 바꾸지 않는다."
```

---

### Task 2: 인증 — 단일 비밀번호와 서명 쿠키

**Files:**
- Create: `apps/web/lib/auth.ts`
- Create: `apps/web/lib/auth.test.ts`
- Create: `apps/web/lib/rate-limit.ts`
- Create: `apps/web/lib/rate-limit.test.ts`
- Create: `apps/web/proxy.ts`
- Create: `apps/web/app/login/page.tsx`
- Create: `apps/web/app/login/login-form.tsx`
- Create: `apps/web/app/api/auth/login/route.ts`
- Create: `apps/web/app/api/auth/logout/route.ts`

**Interfaces:**
- Consumes: `APP_PASSWORD`, `AUTH_SECRET`
- Produces:
  - `createSessionToken(): Promise<string>`
  - `verifySessionToken(token: string | undefined): Promise<boolean>`
  - `SESSION_COOKIE = 'recflow_session'`
  - `checkRateLimit(key: string, now?: number): { allowed: boolean; retryAfterSeconds: number }`

- [ ] **Step 1: 인증 테스트 작성**

`apps/web/lib/auth.test.ts`:

```ts
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

    // 쿼리 접미사(./auth?other)로 캐시를 우회하면 TypeScript가 TS2307을 낸다.
    // 모듈 캐시를 비우고 다시 불러온다.
    vi.resetModules()
    process.env.AUTH_SECRET = 'a-completely-different-secret-key-32chars'
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
```

검증하려는 성질은 "다른 키로 서명된 토큰은 거부된다"이다. 이 테스트가 없으면 `AUTH_SECRET`을 교체해도 기존 세션이 그대로 유효한 문제를 잡지 못한다.

- [ ] **Step 2: 레이트리밋 테스트 작성**

`apps/web/lib/rate-limit.test.ts`:

```ts
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
```

- [ ] **Step 3: 테스트 실패 확인**

```powershell
cd C:\Dev\RECFlow\apps\web
npm run test
```

Expected: FAIL — `Cannot find module './auth'`

- [ ] **Step 4: `lib/auth.ts` 구현**

```ts
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
```

- [ ] **Step 5: `lib/rate-limit.ts` 구현**

```ts
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
```

- [ ] **Step 6: 테스트 통과 확인**

```powershell
npm run test
```

Expected: 13 passed

- [ ] **Step 7: `proxy.ts` 작성 (Next 16 규약)**

파일명은 `middleware.ts`가 **아니다**. export 이름도 `proxy`다.

`apps/web/proxy.ts`:

```ts
import { NextResponse, type NextRequest } from 'next/server'
import { SESSION_COOKIE, verifySessionToken } from '@/lib/auth'

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico|api/auth/login).*)'],
}

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl

  if (pathname === '/login') return NextResponse.next()

  const token = request.cookies.get(SESSION_COOKIE)?.value
  if (await verifySessionToken(token)) return NextResponse.next()

  if (pathname.startsWith('/api/')) {
    return NextResponse.json({ error: '인증이 필요하다' }, { status: 401 })
  }

  const loginUrl = new URL('/login', request.url)
  if (pathname !== '/') loginUrl.searchParams.set('next', pathname)
  return NextResponse.redirect(loginUrl)
}
```

- [ ] **Step 8: 로그인 Route Handler**

`apps/web/app/api/auth/login/route.ts`:

```ts
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
```

`apps/web/app/api/auth/logout/route.ts`:

```ts
import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { SESSION_COOKIE } from '@/lib/auth'

export async function POST() {
  const cookieStore = await cookies()
  cookieStore.delete(SESSION_COOKIE)
  return NextResponse.json({ ok: true })
}
```

- [ ] **Step 9: 로그인 화면**

`apps/web/app/login/page.tsx`:

```tsx
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
```

`apps/web/app/login/login-form.tsx`:

```tsx
'use client'

import { useRouter } from 'next/navigation'
import { useState, type FormEvent } from 'react'

export function LoginForm({ nextPath }: { nextPath: string }) {
  const router = useRouter()
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setPending(true)
    setError(null)

    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ password }),
    })

    if (response.ok) {
      router.replace(nextPath)
      router.refresh()
      return
    }

    const data = (await response.json().catch(() => ({}))) as { error?: string }
    setError(data.error ?? '로그인에 실패했다')
    setPending(false)
  }

  return (
    <form onSubmit={onSubmit} className="mt-8 space-y-4">
      <div>
        <label htmlFor="password" className="block text-sm font-medium">
          비밀번호
        </label>
        <input
          id="password"
          type="password"
          autoComplete="current-password"
          autoFocus
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          className="mt-1.5 w-full rounded-md border border-[var(--color-line)] bg-[var(--color-surface)] px-3 py-2 text-sm outline-none focus:border-[var(--color-accent)]"
        />
      </div>

      {error ? <p className="text-sm text-[var(--color-up)]">{error}</p> : null}

      <button
        type="submit"
        disabled={pending || password.length === 0}
        className="w-full rounded-md bg-[var(--color-accent)] px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
      >
        {pending ? '확인 중…' : '로그인'}
      </button>
    </form>
  )
}
```

- [ ] **Step 10: 수동 확인**

```powershell
cd C:\Dev\RECFlow
npm run dev
```

브라우저에서 확인한다.

1. `http://localhost:3000/dashboard` → `/login?next=/dashboard`로 리다이렉트된다
2. 틀린 비밀번호 → `비밀번호가 올바르지 않다`
3. 6회 연속 실패 → 429와 재시도 안내
4. 맞는 비밀번호 → `/dashboard`로 이동 (아직 화면이 없으므로 404여도 정상)
5. `http://localhost:3000/api/rec/latest` → 로그인 전에는 401 JSON

확인 후 개발 서버를 종료한다.

- [ ] **Step 11: 커밋**

```powershell
git add -A
git commit -m "feat(web): 단일 비밀번호 인증 추가

jose로 서명한 httpOnly 세션 쿠키와 Next 16의 proxy.ts 게이트를 구현했다.
사용자 테이블과 가입 절차는 만들지 않는다.

Next 16에서 middleware.ts는 proxy.ts로 바뀌었고 Node 런타임에서 돈다.
비밀번호는 상수 시간 비교하고 로그인 시도는 IP당 분당 5회로 제한한다.
실패 사유를 세분화하지 않아 공격자에게 정보를 주지 않는다."
```

---

### Task 3: 이동평균과 가격 위치

**Files:**
- Create: `apps/web/lib/analytics/ma.ts`, `apps/web/lib/analytics/ma.test.ts`
- Create: `apps/web/lib/analytics/percentile.ts`, `apps/web/lib/analytics/percentile.test.ts`

**Interfaces:**
- Consumes: 없음 (순수 함수)
- Produces:
  - `movingAverage(series: (number | null)[], window: number): (number | null)[]`
  - `MA_WINDOWS = { MA4: 4, MA8: 8, MA26: 26, MA52: 52, MA104: 104 }`
  - `percentile(current: number, window: number[]): number | null`
  - `MIN_PERCENTILE_SAMPLES = 26`
  - `priceBand(percentileValue: number | null): { key: string; label: string } | null`

- [ ] **Step 1: 이동평균 테스트 작성**

`apps/web/lib/analytics/ma.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { movingAverage } from './ma'

describe('movingAverage', () => {
  it('창 길이만큼 쌓이기 전에는 null이다', () => {
    expect(movingAverage([1, 2, 3], 4)).toEqual([null, null, null])
  })

  it('창이 채워진 시점부터 값을 낸다', () => {
    expect(movingAverage([1, 2, 3, 4], 4)).toEqual([null, null, null, 2.5])
  })

  it('창이 이동한다', () => {
    expect(movingAverage([1, 2, 3, 4, 5], 2)).toEqual([null, 1.5, 2.5, 3.5, 4.5])
  })

  it('빈 배열은 빈 배열이다', () => {
    expect(movingAverage([], 4)).toEqual([])
  })

  it('창 안에 null이 있으면 그 구간은 null이다', () => {
    // 결측을 0이나 직전값으로 메우면 평균이 조용히 왜곡된다.
    expect(movingAverage([1, null, 3, 4], 2)).toEqual([null, null, null, 3.5])
  })

  it('창 크기가 1보다 작으면 예외', () => {
    expect(() => movingAverage([1, 2], 0)).toThrow()
  })

  it('입력 배열을 변경하지 않는다', () => {
    const input = [1, 2, 3]
    movingAverage(input, 2)
    expect(input).toEqual([1, 2, 3])
  })

  it('거래일 인덱스 기준이므로 날짜 간격과 무관하다', () => {
    // 주 2회 거래이므로 캘린더 기준이 아니라 배열 위치 기준이다.
    expect(movingAverage([10, 20, 30, 40], 2)).toEqual([null, 15, 25, 35])
  })
})
```

- [ ] **Step 2: 백분위 테스트 작성**

`apps/web/lib/analytics/percentile.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { MIN_PERCENTILE_SAMPLES, percentile, priceBand } from './percentile'

function series(length: number, start = 1): number[] {
  return Array.from({ length }, (_, index) => start + index)
}

describe('percentile', () => {
  it('표본이 최소 개수 미만이면 null', () => {
    expect(percentile(50, series(MIN_PERCENTILE_SAMPLES - 1))).toBeNull()
  })

  it('최소 개수를 채우면 값을 낸다', () => {
    expect(percentile(50, series(MIN_PERCENTILE_SAMPLES))).not.toBeNull()
  })

  it('최댓값은 100', () => {
    const window = series(30)
    expect(percentile(30, window)).toBe(100)
  })

  it('최솟값은 이하 개수 1건이므로 100/30', () => {
    const window = series(30)
    expect(percentile(1, window)).toBeCloseTo((1 / 30) * 100, 6)
  })

  it('동점은 이하에 산입한다', () => {
    const window = [10, 10, 10, ...series(27, 100)]
    expect(percentile(10, window)).toBeCloseTo((3 / 30) * 100, 6)
  })

  it('창의 최댓값보다 크면 100', () => {
    expect(percentile(999, series(30))).toBe(100)
  })

  it('창의 최솟값보다 작으면 0', () => {
    expect(percentile(-1, series(30))).toBe(0)
  })

  it('빈 창은 null', () => {
    expect(percentile(50, [])).toBeNull()
  })
})

describe('priceBand', () => {
  it('null이면 null', () => {
    expect(priceBand(null)).toBeNull()
  })

  it.each([
    [0, '매우 낮음'],
    [19.9, '매우 낮음'],
    [20, '낮음'],
    [39.9, '낮음'],
    [40, '보통'],
    [59.9, '보통'],
    [60, '높음'],
    [79.9, '높음'],
    [80, '매우 높음'],
    [100, '매우 높음'],
  ])('%s%% -> %s', (value, label) => {
    expect(priceBand(value)?.label).toBe(label)
  })
})
```

- [ ] **Step 3: 테스트 실패 확인**

```powershell
cd C:\Dev\RECFlow\apps\web
npm run test
```

Expected: FAIL — `Cannot find module './ma'`

- [ ] **Step 4: `lib/analytics/ma.ts` 구현**

```ts
/**
 * 거래일 인덱스 기준 단순이동평균.
 *
 * REC 현물시장은 주 2회(화·목) 거래되므로 캘린더 기준이 아니라 배열 위치를 센다.
 * MA8이 약 1개월, MA26이 약 3개월, MA52가 약 6개월에 대응한다.
 */
export const MA_WINDOWS = {
  MA4: 4,
  MA8: 8,
  MA26: 26,
  MA52: 52,
  MA104: 104,
} as const

export type MaWindow = keyof typeof MA_WINDOWS

export function movingAverage(series: (number | null)[], window: number): (number | null)[] {
  if (!Number.isInteger(window) || window < 1) {
    throw new Error(`이동평균 창 크기는 1 이상의 정수여야 한다: ${window}`)
  }

  return series.map((_, index) => {
    if (index + 1 < window) return null

    const slice = series.slice(index + 1 - window, index + 1)
    // 결측이 하나라도 있으면 평균을 내지 않는다. 0이나 직전값으로 메우면
    // 지표가 조용히 왜곡되고, 그 왜곡이 매각 판단 점수까지 전파된다.
    if (slice.some((value) => value === null || !Number.isFinite(value))) return null

    const sum = slice.reduce<number>((total, value) => total + (value as number), 0)
    return sum / window
  })
}
```

- [ ] **Step 5: `lib/analytics/percentile.ts` 구현**

```ts
/**
 * 현재 가격이 과거 분포에서 어디에 있는지 나타낸다.
 *
 * 미래 예측이 아니라 위치 확인이다. 표본이 적으면 위치를 말할 수 없으므로
 * null을 반환한다. 시스템 가동 초기에는 이 값이 없는 것이 정상이다.
 */
export const MIN_PERCENTILE_SAMPLES = 26

export function percentile(current: number, window: number[]): number | null {
  const samples = window.filter((value) => Number.isFinite(value))
  if (samples.length === 0 || samples.length < MIN_PERCENTILE_SAMPLES) return null

  const atOrBelow = samples.filter((value) => value <= current).length
  return (atOrBelow / samples.length) * 100
}

export type PriceBand = { key: 'very-low' | 'low' | 'normal' | 'high' | 'very-high'; label: string }

const BANDS: { min: number; band: PriceBand }[] = [
  { min: 80, band: { key: 'very-high', label: '매우 높음' } },
  { min: 60, band: { key: 'high', label: '높음' } },
  { min: 40, band: { key: 'normal', label: '보통' } },
  { min: 20, band: { key: 'low', label: '낮음' } },
  { min: 0, band: { key: 'very-low', label: '매우 낮음' } },
]

export function priceBand(percentileValue: number | null): PriceBand | null {
  if (percentileValue === null || !Number.isFinite(percentileValue)) return null
  return BANDS.find(({ min }) => percentileValue >= min)?.band ?? null
}
```

- [ ] **Step 6: 테스트 통과 확인**

```powershell
npm run test
```

Expected: 모두 통과 (29 passed 내외)

- [ ] **Step 7: 커밋**

```powershell
git add -A
git commit -m "feat(web): 이동평균과 가격 위치 분석 추가

주 2회 거래이므로 캘린더가 아니라 거래일 인덱스를 센다.

창 안에 결측이 있으면 평균을 내지 않고 null을 반환한다. 0이나 직전값으로
메우면 지표가 조용히 왜곡되고 그 왜곡이 매각 판단 점수까지 전파된다.
백분위도 표본 26개 미만이면 null이다. 가동 초기에 값이 없는 것이 정상이다."
```

---

### Task 4: 평가액과 매각 시뮬레이션

**Files:**
- Create: `apps/web/lib/money.ts`, `apps/web/lib/money.test.ts`
- Create: `apps/web/lib/analytics/valuation.ts`, `apps/web/lib/analytics/valuation.test.ts`
- Create: `apps/web/lib/analytics/simulation.ts`, `apps/web/lib/analytics/simulation.test.ts`

**Interfaces:**
- Consumes: `decimal.js`
- Produces:
  - `toDecimal(value: string | number | null | undefined): Decimal | null`
  - `formatKrw(value: string | number | null, options?: { compact?: boolean }): string`
  - `formatQuantity(value: string | number | null): string`
  - `formatPercent(value: number | null, digits?: number): string`
  - `DASH = '—'`
  - `valuation(input: { holdings: string; unitPrice: string | null }): { amount: string | null }`
  - `simulate(input: { quantity: string; prices: string[]; currentPrice: string | null }): SimulationRow[]`
  - `SimulationRow = { price: string; revenue: string; deltaFromCurrent: string | null }`
  - `simulateTranches(tranches: { quantity: string; price: string }[]): { totalQuantity: string; totalRevenue: string; averagePrice: string | null; rows: TrancheRow[] }`
  - `TrancheRow = { quantity: string; price: string; revenue: string }`

- [ ] **Step 1: 금액 헬퍼 테스트 작성**

`apps/web/lib/money.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { DASH, formatKrw, formatQuantity, toDecimal } from './money'

describe('toDecimal', () => {
  it('문자열을 변환한다', () => {
    expect(toDecimal('71500.25')?.toString()).toBe('71500.25')
  })

  it('null과 undefined는 null', () => {
    expect(toDecimal(null)).toBeNull()
    expect(toDecimal(undefined)).toBeNull()
  })

  it('빈 문자열은 null', () => {
    expect(toDecimal('')).toBeNull()
  })

  it('숫자가 아니면 null', () => {
    expect(toDecimal('abc')).toBeNull()
  })
})

describe('formatKrw', () => {
  it('천 단위 구분자를 넣는다', () => {
    expect(formatKrw('715000000')).toBe('715,000,000원')
  })

  it('null은 대시', () => {
    expect(formatKrw(null)).toBe(DASH)
  })

  it('소수점은 버린다', () => {
    expect(formatKrw('71500.7')).toBe('71,501원')
  })

  it('compact는 억 단위로 줄인다', () => {
    expect(formatKrw('715000000', { compact: true })).toBe('7.15억원')
  })

  it('compact는 1억 미만이면 만 단위', () => {
    expect(formatKrw('12340000', { compact: true })).toBe('1,234만원')
  })
})

describe('formatQuantity', () => {
  it('정수는 소수점을 붙이지 않는다', () => {
    expect(formatQuantity('10000')).toBe('10,000')
  })

  it('소수가 있으면 두 자리까지 보인다', () => {
    expect(formatQuantity('10000.50')).toBe('10,000.5')
  })

  it('null은 대시', () => {
    expect(formatQuantity(null)).toBe(DASH)
  })
})
```

- [ ] **Step 2: 평가액 테스트 작성**

`apps/web/lib/analytics/valuation.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { valuation } from './valuation'

describe('valuation', () => {
  it('보유량 곱하기 시장가격', () => {
    expect(valuation({ holdings: '10000', unitPrice: '71500' }).amount).toBe('715000000')
  })

  it('가격이 없으면 null이다', () => {
    // 수집 데이터가 없을 때 0원이라고 말하지 않는다.
    expect(valuation({ holdings: '10000', unitPrice: null }).amount).toBeNull()
  })

  it('보유량이 0이면 0원', () => {
    expect(valuation({ holdings: '0', unitPrice: '71500' }).amount).toBe('0')
  })

  it('소수 보유량을 정확히 계산한다', () => {
    expect(valuation({ holdings: '1000.55', unitPrice: '71500' }).amount).toBe('71539325')
  })

  it('부동소수점 오차가 생기지 않는다', () => {
    // 0.1 * 3 을 double로 하면 0.30000000000000004 가 된다.
    expect(valuation({ holdings: '0.1', unitPrice: '3' }).amount).toBe('0.3')
  })
})
```

- [ ] **Step 3: 시뮬레이션 테스트 작성**

`apps/web/lib/analytics/simulation.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { simulate, simulateTranches } from './simulation'

describe('simulate', () => {
  it('가격별 예상 매출을 만든다', () => {
    const rows = simulate({ quantity: '10000', prices: ['70000', '75000'], currentPrice: '71500' })
    expect(rows).toHaveLength(2)
    expect(rows[0].revenue).toBe('700000000')
    expect(rows[1].revenue).toBe('750000000')
  })

  it('현재가 대비 증감을 계산한다', () => {
    const rows = simulate({ quantity: '10000', prices: ['75000'], currentPrice: '71500' })
    expect(rows[0].deltaFromCurrent).toBe('35000000')
  })

  it('현재가보다 낮으면 음수 증감', () => {
    const rows = simulate({ quantity: '10000', prices: ['70000'], currentPrice: '71500' })
    expect(rows[0].deltaFromCurrent).toBe('-15000000')
  })

  it('현재가가 없으면 증감은 null이고 매출은 계산된다', () => {
    const rows = simulate({ quantity: '10000', prices: ['70000'], currentPrice: null })
    expect(rows[0].revenue).toBe('700000000')
    expect(rows[0].deltaFromCurrent).toBeNull()
  })

  it('가격 목록이 비면 빈 배열', () => {
    expect(simulate({ quantity: '10000', prices: [], currentPrice: '71500' })).toEqual([])
  })

  it('잘못된 가격은 건너뛴다', () => {
    const rows = simulate({ quantity: '10000', prices: ['70000', 'abc'], currentPrice: null })
    expect(rows).toHaveLength(1)
  })
})

describe('simulateTranches', () => {
  const tranches = [
    { quantity: '3000', price: '72000' },
    { quantity: '3000', price: '75000' },
    { quantity: '4000', price: '78000' },
  ]

  it('총 수량과 총 매출을 계산한다', () => {
    const result = simulateTranches(tranches)
    expect(result.totalQuantity).toBe('10000')
    expect(result.totalRevenue).toBe('753000000')
  })

  it('평균 매도가는 수량 가중평균이다', () => {
    // 단순 산술평균은 75000이지만 가중평균은 75300이다.
    const result = simulateTranches(tranches)
    expect(result.averagePrice).toBe('75300')
  })

  it('각 회차 매출을 낸다', () => {
    const result = simulateTranches(tranches)
    expect(result.rows.map((row) => row.revenue)).toEqual(['216000000', '225000000', '312000000'])
  })

  it('빈 목록이면 0이고 평균가는 null', () => {
    const result = simulateTranches([])
    expect(result.totalQuantity).toBe('0')
    expect(result.totalRevenue).toBe('0')
    expect(result.averagePrice).toBeNull()
  })

  it('총 수량이 0이면 평균가는 null이다', () => {
    // 0으로 나누어 Infinity나 NaN을 만들지 않는다.
    const result = simulateTranches([{ quantity: '0', price: '72000' }])
    expect(result.averagePrice).toBeNull()
  })
})
```

- [ ] **Step 4: 테스트 실패 확인**

```powershell
npm run test
```

Expected: FAIL — `Cannot find module './money'`

- [ ] **Step 5: `lib/money.ts` 구현**

```ts
import Decimal from 'decimal.js'

export const DASH = '—'

export function toDecimal(value: string | number | null | undefined): Decimal | null {
  if (value === null || value === undefined) return null
  const text = String(value).trim()
  if (text === '') return null
  try {
    const decimal = new Decimal(text)
    return decimal.isFinite() ? decimal : null
  } catch {
    return null
  }
}

export function formatKrw(
  value: string | number | null | undefined,
  options: { compact?: boolean } = {},
): string {
  const decimal = toDecimal(value)
  if (decimal === null) return DASH

  if (options.compact) {
    const absolute = decimal.abs()
    if (absolute.gte(100_000_000)) {
      return `${trimZeros(decimal.div(100_000_000).toFixed(2))}억원`
    }
    if (absolute.gte(10_000)) {
      return `${group(decimal.div(10_000).toFixed(0))}만원`
    }
  }

  return `${group(decimal.toFixed(0))}원`
}

export function formatQuantity(value: string | number | null | undefined): string {
  const decimal = toDecimal(value)
  if (decimal === null) return DASH
  return group(trimZeros(decimal.toFixed(2)))
}

export function formatPercent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return DASH
  return `${value.toFixed(digits)}%`
}

function group(text: string): string {
  const negative = text.startsWith('-')
  const [integer, fraction] = (negative ? text.slice(1) : text).split('.')
  const grouped = integer.replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  const result = fraction ? `${grouped}.${fraction}` : grouped
  return negative ? `-${result}` : result
}

function trimZeros(text: string): string {
  return text.includes('.') ? text.replace(/\.?0+$/, '') : text
}
```

- [ ] **Step 6: `lib/analytics/valuation.ts` 구현**

```ts
import { toDecimal } from '@/lib/money'

/**
 * 보유 REC의 현재 평가액.
 *
 * rec_inventory.rec_quantity 는 가중치가 이미 적용된 발급 수량이므로
 * 여기서 가중치를 다시 곱하지 않는다.
 */
export function valuation(input: {
  holdings: string
  unitPrice: string | null
}): { amount: string | null } {
  const holdings = toDecimal(input.holdings)
  const unitPrice = toDecimal(input.unitPrice)

  // 시세가 없을 때 0원이라고 말하지 않는다. 모른다고 말한다.
  if (holdings === null || unitPrice === null) return { amount: null }

  return { amount: holdings.mul(unitPrice).toString() }
}
```

- [ ] **Step 7: `lib/analytics/simulation.ts` 구현**

```ts
import Decimal from 'decimal.js'
import { toDecimal } from '@/lib/money'

export type SimulationRow = {
  price: string
  revenue: string
  deltaFromCurrent: string | null
}

export type TrancheInput = { quantity: string; price: string }
export type TrancheRow = { quantity: string; price: string; revenue: string }

export function simulate(input: {
  quantity: string
  prices: string[]
  currentPrice: string | null
}): SimulationRow[] {
  const quantity = toDecimal(input.quantity)
  if (quantity === null) return []

  const currentPrice = toDecimal(input.currentPrice)
  const currentRevenue = currentPrice === null ? null : quantity.mul(currentPrice)

  return input.prices
    .map((raw) => {
      const price = toDecimal(raw)
      if (price === null) return null

      const revenue = quantity.mul(price)
      return {
        price: price.toString(),
        revenue: revenue.toString(),
        deltaFromCurrent: currentRevenue === null ? null : revenue.minus(currentRevenue).toString(),
      }
    })
    .filter((row): row is SimulationRow => row !== null)
}

export function simulateTranches(tranches: TrancheInput[]): {
  totalQuantity: string
  totalRevenue: string
  averagePrice: string | null
  rows: TrancheRow[]
} {
  const rows: TrancheRow[] = []
  let totalQuantity = new Decimal(0)
  let totalRevenue = new Decimal(0)

  for (const tranche of tranches) {
    const quantity = toDecimal(tranche.quantity)
    const price = toDecimal(tranche.price)
    if (quantity === null || price === null) continue

    const revenue = quantity.mul(price)
    rows.push({ quantity: quantity.toString(), price: price.toString(), revenue: revenue.toString() })
    totalQuantity = totalQuantity.plus(quantity)
    totalRevenue = totalRevenue.plus(revenue)
  }

  // 회차별 수량이 다르면 산술평균은 틀린다. 수량 가중평균을 쓴다.
  // 총 수량이 0이면 나눌 수 없으므로 null이다. Infinity나 NaN을 만들지 않는다.
  const averagePrice = totalQuantity.isZero() ? null : totalRevenue.div(totalQuantity).toString()

  return {
    totalQuantity: totalQuantity.toString(),
    totalRevenue: totalRevenue.toString(),
    averagePrice,
    rows,
  }
}
```

- [ ] **Step 8: 테스트 통과 확인**

```powershell
npm run test
```

Expected: 모두 통과 (52 passed 내외)

- [ ] **Step 9: 커밋**

```powershell
git add -A
git commit -m "feat(web): 평가액과 매각 시뮬레이션 추가

금액은 전부 decimal.js로 계산하고 문자열로 화면에 전달한다.
부동소수점 오차가 원 단위 금액에 닿지 않게 한다.

분할매각 평균 매도가는 수량 가중평균이다. 회차별 수량이 다르면
산술평균은 틀린 값을 준다. 총 수량이 0이면 null을 반환해
Infinity나 NaN이 화면에 나가지 않게 한다.

시세가 없으면 평가액은 0원이 아니라 null이다."
```

---

### Task 5: 매각 판단 점수

**Files:**
- Create: `apps/web/lib/analytics/score.ts`, `apps/web/lib/analytics/score.test.ts`

**Interfaces:**
- Consumes: Task 3의 `percentile`
- Produces:
  - `decisionScore(input: ScoreInput): ScoreResult`
  - `ScoreInput = { percentile: number | null; currentPrice: number | null; ma8: number | null; ma26: number | null; recentVolume: number | null; averageVolume3m: number | null }`
  - `ScoreResult = { total: number | null; breakdown: { position: number | null; trend: number | null; volume: number | null }; label: string; complete: boolean }`

- [ ] **Step 1: 테스트 작성**

`apps/web/lib/analytics/score.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { decisionScore } from './score'

function input(overrides: Partial<Parameters<typeof decisionScore>[0]> = {}) {
  return {
    percentile: 50,
    currentPrice: 71000,
    ma8: 70000,
    ma26: 69000,
    recentVolume: 100000,
    averageVolume3m: 100000,
    ...overrides,
  }
}

describe('가격 위치 점수', () => {
  it.each([
    [90, 2],
    [80, 2],
    [70, 1],
    [60, 1],
    [50, 0],
    [40, 0],
    [30, -1],
    [20, -1],
    [10, -2],
  ])('백분위 %s -> %s점', (value, expected) => {
    expect(decisionScore(input({ percentile: value })).breakdown.position).toBe(expected)
  })
})

describe('추세 점수', () => {
  it('현재가 > MA8 > MA26 이면 +2', () => {
    const result = decisionScore(input({ currentPrice: 72000, ma8: 71000, ma26: 70000 }))
    expect(result.breakdown.trend).toBe(2)
  })

  it('현재가가 MA26 위지만 정배열이 아니면 +1', () => {
    const result = decisionScore(input({ currentPrice: 72000, ma8: 73000, ma26: 70000 }))
    expect(result.breakdown.trend).toBe(1)
  })

  it('현재가 < MA8 < MA26 이면 -2', () => {
    const result = decisionScore(input({ currentPrice: 68000, ma8: 69000, ma26: 70000 }))
    expect(result.breakdown.trend).toBe(-2)
  })

  it('현재가가 MA26 아래면 -1', () => {
    const result = decisionScore(input({ currentPrice: 68000, ma8: 67000, ma26: 70000 }))
    expect(result.breakdown.trend).toBe(-1)
  })

  it('현재가가 MA26과 같으면 0', () => {
    const result = decisionScore(input({ currentPrice: 70000, ma8: 71000, ma26: 70000 }))
    expect(result.breakdown.trend).toBe(0)
  })
})

describe('거래량 점수', () => {
  it('3개월 평균의 1.2배를 넘으면 +1', () => {
    expect(decisionScore(input({ recentVolume: 121, averageVolume3m: 100 })).breakdown.volume).toBe(1)
  })

  it('평균 수준이면 0', () => {
    expect(decisionScore(input({ recentVolume: 100, averageVolume3m: 100 })).breakdown.volume).toBe(0)
  })

  it('평균의 0.7배 미만이면 -1', () => {
    expect(decisionScore(input({ recentVolume: 60, averageVolume3m: 100 })).breakdown.volume).toBe(-1)
  })

  it('평균 거래량이 0이면 null이다', () => {
    expect(decisionScore(input({ averageVolume3m: 0 })).breakdown.volume).toBeNull()
  })
})

describe('데이터 부족 처리', () => {
  it('구성요소가 하나라도 없으면 총점은 null이다', () => {
    const result = decisionScore(input({ percentile: null }))
    expect(result.total).toBeNull()
    expect(result.complete).toBe(false)
    expect(result.label).toBe('데이터 부족')
  })

  it('계산 가능한 구성요소는 그대로 보여준다', () => {
    // 총점을 못 내도 아는 것까지는 보여준다.
    const result = decisionScore(input({ percentile: null }))
    expect(result.breakdown.trend).not.toBeNull()
    expect(result.breakdown.volume).not.toBeNull()
  })

  it('MA26이 없으면 추세는 null이다', () => {
    expect(decisionScore(input({ ma26: null })).breakdown.trend).toBeNull()
  })
})

describe('종합 판정', () => {
  it('최고 조합은 +5점 적극 매도 검토', () => {
    const result = decisionScore(input({
      percentile: 90, currentPrice: 72000, ma8: 71000, ma26: 70000,
      recentVolume: 200, averageVolume3m: 100,
    }))
    expect(result.total).toBe(5)
    expect(result.label).toBe('적극 매도 검토')
    expect(result.complete).toBe(true)
  })

  it('+2점이면 일부 매도 검토', () => {
    // 위치 +1, 추세 +1, 거래량 0
    const result = decisionScore(input({
      percentile: 70, currentPrice: 72000, ma8: 73000, ma26: 70000,
      recentVolume: 100, averageVolume3m: 100,
    }))
    expect(result.total).toBe(2)
    expect(result.label).toBe('일부 매도 검토')
  })

  it('0점이면 관망', () => {
    // 위치 0, 추세 0, 거래량 0
    const result = decisionScore(input({
      percentile: 50, currentPrice: 70000, ma8: 71000, ma26: 70000,
      recentVolume: 100, averageVolume3m: 100,
    }))
    expect(result.total).toBe(0)
    expect(result.label).toBe('관망')
  })

  it('-2점이면 매도 신중', () => {
    // 위치 -1, 추세 -1, 거래량 0
    const result = decisionScore(input({
      percentile: 30, currentPrice: 68000, ma8: 67000, ma26: 70000,
      recentVolume: 100, averageVolume3m: 100,
    }))
    expect(result.total).toBe(-2)
    expect(result.label).toBe('매도 신중')
  })

  it('최저 조합은 -5점 매도 신중', () => {
    const result = decisionScore(input({
      percentile: 5, currentPrice: 68000, ma8: 69000, ma26: 70000,
      recentVolume: 10, averageVolume3m: 100,
    }))
    expect(result.total).toBe(-5)
    expect(result.label).toBe('매도 신중')
  })
})
```

- [ ] **Step 2: 테스트 실패 확인**

```powershell
npm run test
```

Expected: FAIL — `Cannot find module './score'`

- [ ] **Step 3: `lib/analytics/score.ts` 구현**

```ts
/**
 * 매각 판단 보조지표.
 *
 * 가격 예측 모델이 아니다. 가격 위치·추세·거래량이라는 세 가지 관찰 가능한
 * 사실을 규칙으로 점수화해 "왜 이 점수인지" 설명할 수 있게 한 것이다.
 * 회사 내부 매각 의사결정의 참고자료로만 쓴다.
 *
 * 구성요소 중 하나라도 계산할 수 없으면 총점을 내지 않는다. 모르는 것을
 * 0으로 채워 그럴듯한 총점을 만드는 것이 이 시스템의 가장 나쁜 실패다.
 */

export type ScoreInput = {
  percentile: number | null
  currentPrice: number | null
  ma8: number | null
  ma26: number | null
  recentVolume: number | null
  averageVolume3m: number | null
}

export type ScoreBreakdown = {
  position: number | null
  trend: number | null
  volume: number | null
}

export type ScoreResult = {
  total: number | null
  breakdown: ScoreBreakdown
  label: string
  complete: boolean
}

export const INSUFFICIENT_LABEL = '데이터 부족'

const VOLUME_SURGE_RATIO = 1.2
const VOLUME_SLUMP_RATIO = 0.7

export function decisionScore(input: ScoreInput): ScoreResult {
  const breakdown: ScoreBreakdown = {
    position: positionScore(input.percentile),
    trend: trendScore(input.currentPrice, input.ma8, input.ma26),
    volume: volumeScore(input.recentVolume, input.averageVolume3m),
  }

  const parts = [breakdown.position, breakdown.trend, breakdown.volume]
  const complete = parts.every((value) => value !== null)

  if (!complete) {
    return { total: null, breakdown, label: INSUFFICIENT_LABEL, complete: false }
  }

  const total = parts.reduce<number>((sum, value) => sum + (value as number), 0)
  return { total, breakdown, label: labelFor(total), complete: true }
}

function positionScore(percentileValue: number | null): number | null {
  if (percentileValue === null || !Number.isFinite(percentileValue)) return null
  if (percentileValue >= 80) return 2
  if (percentileValue >= 60) return 1
  if (percentileValue >= 40) return 0
  if (percentileValue >= 20) return -1
  return -2
}

function trendScore(current: number | null, ma8: number | null, ma26: number | null): number | null {
  if (current === null || ma26 === null) return null

  if (ma8 !== null && current > ma8 && ma8 > ma26) return 2
  if (current > ma26) return 1
  if (ma8 !== null && current < ma8 && ma8 < ma26) return -2
  if (current < ma26) return -1
  return 0
}

function volumeScore(recent: number | null, average: number | null): number | null {
  if (recent === null || average === null || !Number.isFinite(average) || average <= 0) return null

  const ratio = recent / average
  if (ratio >= VOLUME_SURGE_RATIO) return 1
  if (ratio < VOLUME_SLUMP_RATIO) return -1
  return 0
}

function labelFor(total: number): string {
  if (total >= 4) return '적극 매도 검토'
  if (total >= 2) return '일부 매도 검토'
  if (total >= -1) return '관망'
  return '매도 신중'
}
```

- [ ] **Step 4: 테스트 통과 확인**

```powershell
npm run test
```

Expected: 모두 통과

- [ ] **Step 5: 커밋**

```powershell
git add -A
git commit -m "feat(web): 매각 판단 점수 추가

가격 위치, 추세, 거래량을 규칙으로 점수화한 설명 가능한 보조지표다.
예측 모델이 아니다.

구성요소 중 하나라도 계산할 수 없으면 총점을 내지 않고 데이터 부족으로
표시한다. 모르는 것을 0으로 채워 그럴듯한 총점을 만들면 사용자가
근거 없는 확신을 갖게 된다. 아는 구성요소는 그대로 보여준다."
```

---

### Task 6: 데이터 접근 계층과 시장 API

**Files:**
- Create: `apps/web/lib/types.ts`
- Create: `apps/web/lib/queries/market.ts`
- Create: `apps/web/lib/queries/company.ts`
- Create: `apps/web/lib/period.ts`, `apps/web/lib/period.test.ts`
- Create: `apps/web/app/api/rec/latest/route.ts`
- Create: `apps/web/app/api/rec/history/route.ts`
- Create: `apps/web/app/api/rec/stats/route.ts`

**Interfaces:**
- Consumes: `prisma` (Task 1), 계획 A의 테이블
- Produces:
  - `MarketPoint = { tradeDate: string; avgPrice: number | null; closePrice: number | null; highPrice: number | null; lowPrice: number | null; volume: number | null; tradeAmount: string | null; tradeCount: number | null }`
  - `getLatestMarket(area?): Promise<MarketPoint | null>`
  - `getMarketHistory(options: { from?: Date; to?: Date; area?: MarketArea }): Promise<MarketPoint[]>`
  - `getMarketStats(): Promise<MarketStats>` — 최근값, 직전 거래일 대비, 1/3/12개월 평균, 1년 최고·최저
  - `getHoldingsSummary(): Promise<{ issued: string; sold: string; holdings: string; byPlant: PlantHolding[] }>`
  - `PERIODS`, `resolvePeriod(key: string | undefined, today?: Date): { key: PeriodKey; from: Date | null }`

- [ ] **Step 1: 기간 해석 테스트 작성**

`apps/web/lib/period.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { PERIOD_KEYS, resolvePeriod } from './period'

const TODAY = new Date('2026-08-13T00:00:00Z')

describe('resolvePeriod', () => {
  it('기본값은 1년이다', () => {
    expect(resolvePeriod(undefined, TODAY).key).toBe('1Y')
  })

  it('알 수 없는 값도 기본값으로 떨어진다', () => {
    expect(resolvePeriod('nonsense', TODAY).key).toBe('1Y')
  })

  it('ALL은 시작일이 없다', () => {
    expect(resolvePeriod('ALL', TODAY).from).toBeNull()
  })

  it('1M은 한 달 전이다', () => {
    expect(resolvePeriod('1M', TODAY).from?.toISOString().slice(0, 10)).toBe('2026-07-13')
  })

  it('3Y는 3년 전이다', () => {
    expect(resolvePeriod('3Y', TODAY).from?.toISOString().slice(0, 10)).toBe('2023-08-13')
  })

  it('모든 키를 해석할 수 있다', () => {
    for (const key of PERIOD_KEYS) {
      expect(resolvePeriod(key, TODAY).key).toBe(key)
    }
  })
})
```

- [ ] **Step 2: 테스트 실패 확인 후 `lib/period.ts` 구현**

```powershell
npm run test
```

Expected: FAIL — `Cannot find module './period'`

`apps/web/lib/period.ts`:

```ts
export const PERIOD_KEYS = ['1M', '3M', '6M', '1Y', '3Y', 'ALL'] as const
export type PeriodKey = (typeof PERIOD_KEYS)[number]

export const DEFAULT_PERIOD: PeriodKey = '1Y'

const MONTHS: Record<Exclude<PeriodKey, 'ALL'>, number> = {
  '1M': 1,
  '3M': 3,
  '6M': 6,
  '1Y': 12,
  '3Y': 36,
}

export const PERIOD_LABELS: Record<PeriodKey, string> = {
  '1M': '1개월',
  '3M': '3개월',
  '6M': '6개월',
  '1Y': '1년',
  '3Y': '3년',
  ALL: '전체',
}

export function resolvePeriod(
  key: string | undefined,
  today: Date = new Date(),
): { key: PeriodKey; from: Date | null } {
  const resolved = (PERIOD_KEYS as readonly string[]).includes(key ?? '')
    ? (key as PeriodKey)
    : DEFAULT_PERIOD

  if (resolved === 'ALL') return { key: resolved, from: null }

  const from = new Date(today)
  from.setUTCMonth(from.getUTCMonth() - MONTHS[resolved])
  return { key: resolved, from }
}
```

- [ ] **Step 3: 테스트 통과 확인**

```powershell
npm run test
```

Expected: 모두 통과

- [ ] **Step 4: `lib/types.ts` 작성**

```ts
export type MarketArea = 'LAND' | 'JEJU' | 'TOTAL'

/**
 * Prisma의 Decimal은 JSON 직렬화도 Server → Client 전달도 되지 않는다.
 * lib/queries 가 이 타입으로 변환한 뒤에야 화면으로 나간다.
 *
 * 가격과 거래량은 차트 좌표 계산에 쓰이므로 number,
 * 거래금액은 조 단위까지 커질 수 있어 문자열로 둔다.
 */
export type MarketPoint = {
  tradeDate: string
  avgPrice: number | null
  closePrice: number | null
  highPrice: number | null
  lowPrice: number | null
  volume: number | null
  tradeAmount: string | null
  tradeCount: number | null
}

export type MarketStats = {
  latest: MarketPoint | null
  previous: MarketPoint | null
  changeRate: number | null
  average1m: number | null
  average3m: number | null
  average12m: number | null
  high1y: number | null
  low1y: number | null
}

export type PlantHolding = {
  plantId: number
  plantName: string
  issued: string
  sold: string
  holdings: string
}
```

- [ ] **Step 5: `lib/queries/market.ts` 작성**

```ts
import type { Prisma } from '@prisma/client'
import { prisma } from '@/lib/db'
import type { MarketArea, MarketPoint, MarketStats } from '@/lib/types'

type MarketRow = {
  tradeDate: Date
  avgPrice: Prisma.Decimal | null
  closePrice: Prisma.Decimal | null
  highPrice: Prisma.Decimal | null
  lowPrice: Prisma.Decimal | null
  volume: Prisma.Decimal | null
  tradeAmount: Prisma.Decimal | null
  tradeCount: number | null
}

/** Decimal이 화면으로 새어나가지 않게 막는 유일한 지점이다. */
function toPoint(row: MarketRow): MarketPoint {
  return {
    tradeDate: row.tradeDate.toISOString().slice(0, 10),
    avgPrice: row.avgPrice === null ? null : row.avgPrice.toNumber(),
    closePrice: row.closePrice === null ? null : row.closePrice.toNumber(),
    highPrice: row.highPrice === null ? null : row.highPrice.toNumber(),
    lowPrice: row.lowPrice === null ? null : row.lowPrice.toNumber(),
    volume: row.volume === null ? null : row.volume.toNumber(),
    tradeAmount: row.tradeAmount === null ? null : row.tradeAmount.toString(),
    tradeCount: row.tradeCount,
  }
}

const SELECT = {
  tradeDate: true,
  avgPrice: true,
  closePrice: true,
  highPrice: true,
  lowPrice: true,
  volume: true,
  tradeAmount: true,
  tradeCount: true,
} as const

export async function getLatestMarket(area: MarketArea = 'TOTAL'): Promise<MarketPoint | null> {
  const row = await prisma.recMarket.findFirst({
    where: { marketArea: area },
    orderBy: { tradeDate: 'desc' },
    select: SELECT,
  })
  return row ? toPoint(row) : null
}

export async function getMarketHistory(options: {
  from?: Date | null
  to?: Date | null
  area?: MarketArea
} = {}): Promise<MarketPoint[]> {
  const rows = await prisma.recMarket.findMany({
    where: {
      marketArea: options.area ?? 'TOTAL',
      ...(options.from || options.to
        ? {
            tradeDate: {
              ...(options.from ? { gte: options.from } : {}),
              ...(options.to ? { lte: options.to } : {}),
            },
          }
        : {}),
    },
    orderBy: { tradeDate: 'asc' },
    select: SELECT,
  })
  return rows.map(toPoint)
}

export async function getMarketStats(today: Date = new Date()): Promise<MarketStats> {
  const recent = await prisma.recMarket.findMany({
    where: { marketArea: 'TOTAL' },
    orderBy: { tradeDate: 'desc' },
    take: 2,
    select: SELECT,
  })

  const latest = recent[0] ? toPoint(recent[0]) : null
  const previous = recent[1] ? toPoint(recent[1]) : null

  const changeRate =
    latest?.avgPrice != null && previous?.avgPrice != null && previous.avgPrice !== 0
      ? ((latest.avgPrice - previous.avgPrice) / previous.avgPrice) * 100
      : null

  const [average1m, average3m, average12m] = await Promise.all([
    averageSince(monthsAgo(today, 1)),
    averageSince(monthsAgo(today, 3)),
    averageSince(monthsAgo(today, 12)),
  ])

  const range = await prisma.recMarket.aggregate({
    where: { marketArea: 'TOTAL', tradeDate: { gte: monthsAgo(today, 12) } },
    _max: { avgPrice: true },
    _min: { avgPrice: true },
  })

  return {
    latest,
    previous,
    changeRate,
    average1m,
    average3m,
    average12m,
    high1y: range._max.avgPrice?.toNumber() ?? null,
    low1y: range._min.avgPrice?.toNumber() ?? null,
  }
}

async function averageSince(from: Date): Promise<number | null> {
  const result = await prisma.recMarket.aggregate({
    where: { marketArea: 'TOTAL', tradeDate: { gte: from } },
    _avg: { avgPrice: true },
  })
  return result._avg.avgPrice?.toNumber() ?? null
}

function monthsAgo(today: Date, months: number): Date {
  const date = new Date(today)
  date.setUTCMonth(date.getUTCMonth() - months)
  return date
}
```

- [ ] **Step 6: `lib/queries/company.ts` 작성**

```ts
import Decimal from 'decimal.js'
import { prisma } from '@/lib/db'
import type { PlantHolding } from '@/lib/types'

/**
 * 보유량은 저장하지 않고 계산한다.
 *   발급 = Σ rec_inventory.rec_quantity (expired_at IS NULL)
 *   매각 = Σ rec_sales.quantity
 *   보유 = 발급 − 매각
 * 상태 컬럼을 두면 부분 매각을 표현할 수 없고 매각 내역과 어긋난다.
 */
export async function getHoldingsSummary(): Promise<{
  issued: string
  sold: string
  holdings: string
  byPlant: PlantHolding[]
}> {
  const [plants, issuedRows, soldRows] = await Promise.all([
    prisma.plant.findMany({ orderBy: { name: 'asc' }, select: { id: true, name: true } }),
    prisma.recInventory.groupBy({
      by: ['plantId'],
      where: { expiredAt: null },
      _sum: { recQuantity: true },
    }),
    prisma.recSale.groupBy({ by: ['plantId'], _sum: { quantity: true } }),
  ])

  const issuedByPlant = new Map(issuedRows.map((row) => [row.plantId, row._sum.recQuantity]))
  const soldByPlant = new Map(soldRows.map((row) => [row.plantId, row._sum.quantity]))

  let totalIssued = new Decimal(0)
  let totalSold = new Decimal(0)

  const byPlant: PlantHolding[] = plants.map((plant) => {
    const issued = new Decimal(issuedByPlant.get(plant.id)?.toString() ?? '0')
    const sold = new Decimal(soldByPlant.get(plant.id)?.toString() ?? '0')
    totalIssued = totalIssued.plus(issued)
    totalSold = totalSold.plus(sold)

    return {
      plantId: plant.id,
      plantName: plant.name,
      issued: issued.toString(),
      sold: sold.toString(),
      holdings: issued.minus(sold).toString(),
    }
  })

  return {
    issued: totalIssued.toString(),
    sold: totalSold.toString(),
    holdings: totalIssued.minus(totalSold).toString(),
    byPlant,
  }
}

export async function getActiveTargets() {
  const targets = await prisma.priceTarget.findMany({
    where: { isActive: true },
    orderBy: { targetPrice: 'asc' },
  })
  return targets.map((target) => ({
    id: target.id,
    name: target.name,
    targetPrice: target.targetPrice.toString(),
  }))
}
```

- [ ] **Step 7: 시장 Route Handler 작성**

`apps/web/app/api/rec/latest/route.ts`:

```ts
import { NextResponse } from 'next/server'
import { getLatestMarket } from '@/lib/queries/market'

export async function GET() {
  const latest = await getLatestMarket()
  if (!latest) return NextResponse.json({ error: '수집된 데이터가 없다' }, { status: 404 })
  return NextResponse.json(latest)
}
```

`apps/web/app/api/rec/history/route.ts`:

```ts
import { NextResponse, type NextRequest } from 'next/server'
import { getMarketHistory } from '@/lib/queries/market'
import { resolvePeriod } from '@/lib/period'
import type { MarketArea } from '@/lib/types'

const AREAS: MarketArea[] = ['LAND', 'JEJU', 'TOTAL']

export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams
  const { key, from } = resolvePeriod(params.get('period') ?? undefined)

  const requestedArea = params.get('area') as MarketArea | null
  const area = requestedArea && AREAS.includes(requestedArea) ? requestedArea : 'TOTAL'

  const points = await getMarketHistory({ from, area })
  return NextResponse.json({ period: key, area, count: points.length, points })
}
```

`apps/web/app/api/rec/stats/route.ts`:

```ts
import { NextResponse } from 'next/server'
import { getMarketStats } from '@/lib/queries/market'

export async function GET() {
  return NextResponse.json(await getMarketStats())
}
```

- [ ] **Step 8: 실제 데이터로 확인**

```powershell
cd C:\Dev\RECFlow
npm run dev
```

다른 PowerShell 창에서 로그인 쿠키 없이 401이 나오는지, 브라우저에서 로그인 후 아래가 실제 값을 돌려주는지 확인한다.

```text
http://localhost:3000/api/rec/latest      → 2026-08-11 전후의 시세
http://localhost:3000/api/rec/stats       → average1m/3m/12m, high1y, low1y가 채워짐
http://localhost:3000/api/rec/history?period=3M  → count가 20~30 사이
http://localhost:3000/api/rec/history?period=ALL → count가 313
http://localhost:3000/api/rec/history?area=LAND  → closePrice가 전부 null
```

`area=LAND`에서 `closePrice`가 `null`인 것이 정상이다. 종가는 통합값으로만 제공된다.

- [ ] **Step 9: 커밋**

```powershell
git add -A
git commit -m "feat(web): 데이터 접근 계층과 시장 API 추가

Prisma의 Decimal은 직렬화되지 않으므로 lib/queries에서만 평범한 객체로
변환한다. 이 경계 밖에서는 Decimal을 만지지 않는다.

가격과 거래량은 차트 좌표에 쓰이므로 number, 거래금액은 자릿수가 커서
문자열로 둔다. 보유량은 발급에서 매각을 빼서 계산하며 저장하지 않는다."
```

---

### Task 7: 공용 UI 컴포넌트와 대시보드

**Files:**
- Create: `apps/web/components/ui/card.tsx`, `stat.tsx`, `button.tsx`, `table.tsx`, `empty.tsx`, `badge.tsx`
- Create: `apps/web/components/charts/price-chart.tsx`
- Create: `apps/web/components/app-nav.tsx`
- Create: `apps/web/app/(app)/layout.tsx`
- Create: `apps/web/app/(app)/dashboard/page.tsx`
- Modify: `apps/web/app/page.tsx`

**Interfaces:**
- Consumes: Task 3~6 전부
- Produces: `/dashboard` 화면, 재사용 가능한 UI 프리미티브, `PriceChart` 클라이언트 컴포넌트

> **shadcn/ui 대신 손으로 쓴 프리미티브를 쓴다.** shadcn CLI는 대화형 프롬프트를 띄워 자동화된 작업자 환경에서 멈출 수 있다. 화면이 7개뿐이고 필요한 프리미티브가 6개라 직접 작성하는 편이 안전하다. API 형태는 shadcn과 비슷하게 맞춰 나중에 교체할 수 있게 한다.

- [ ] **Step 1: UI 프리미티브 작성**

`apps/web/components/ui/card.tsx`:

```tsx
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
```

`apps/web/components/ui/stat.tsx`:

```tsx
import { DASH } from '@/lib/money'

export function Stat({
  label,
  value,
  sub,
  tone = 'neutral',
}: {
  label: string
  value: string
  sub?: string | null
  tone?: 'neutral' | 'up' | 'down'
}) {
  const toneClass =
    tone === 'up'
      ? 'text-[var(--color-up)]'
      : tone === 'down'
        ? 'text-[var(--color-down)]'
        : ''

  return (
    <div>
      <p className="text-sm text-[var(--color-muted)]">{label}</p>
      <p className={`tabular mt-1 text-2xl font-semibold tracking-tight ${toneClass}`}>{value}</p>
      {sub ? <p className="tabular mt-0.5 text-sm text-[var(--color-muted)]">{sub}</p> : null}
      {value === DASH ? (
        <p className="mt-0.5 text-xs text-[var(--color-muted)]">데이터 부족</p>
      ) : null}
    </div>
  )
}
```

`apps/web/components/ui/empty.tsx` — 빈 상태를 오류가 아니라 1급 상태로 다룬다.

```tsx
export function Empty({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-dashed border-[var(--color-line)] p-10 text-center">
      <p className="text-sm font-medium">{title}</p>
      {hint ? <p className="mt-1 text-sm text-[var(--color-muted)]">{hint}</p> : null}
    </div>
  )
}
```

`apps/web/components/ui/button.tsx`:

```tsx
type Props = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'ghost'
}

export function Button({ variant = 'primary', className = '', ...props }: Props) {
  const base = 'rounded-md px-3 py-1.5 text-sm font-medium disabled:opacity-50'
  const styles =
    variant === 'primary'
      ? 'bg-[var(--color-accent)] text-white'
      : 'border border-[var(--color-line)] hover:bg-[var(--color-canvas)]'
  return <button className={`${base} ${styles} ${className}`} {...props} />
}
```

`apps/web/components/ui/table.tsx`:

```tsx
export function Table({ children }: { children: React.ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">{children}</table>
    </div>
  )
}

export function Th({ children, align = 'left' }: { children: React.ReactNode; align?: 'left' | 'right' }) {
  return (
    <th
      className={`border-b border-[var(--color-line)] pb-2 font-medium text-[var(--color-muted)] ${align === 'right' ? 'text-right' : 'text-left'}`}
    >
      {children}
    </th>
  )
}

export function Td({ children, align = 'left' }: { children: React.ReactNode; align?: 'left' | 'right' }) {
  return (
    <td
      className={`tabular border-b border-[var(--color-line)] py-2 ${align === 'right' ? 'text-right' : 'text-left'}`}
    >
      {children}
    </td>
  )
}
```

`apps/web/components/ui/badge.tsx`:

```tsx
export function Badge({ children, tone = 'neutral' }: { children: React.ReactNode; tone?: 'neutral' | 'up' | 'down' }) {
  const styles =
    tone === 'up'
      ? 'bg-[var(--color-up)]/10 text-[var(--color-up)]'
      : tone === 'down'
        ? 'bg-[var(--color-down)]/10 text-[var(--color-down)]'
        : 'bg-[var(--color-muted)]/10 text-[var(--color-muted)]'
  return <span className={`rounded px-2 py-0.5 text-xs font-medium ${styles}`}>{children}</span>
}
```

- [ ] **Step 2: 가격 차트 컴포넌트**

`apps/web/components/charts/price-chart.tsx` — Recharts는 브라우저에서만 동작하므로 클라이언트 컴포넌트다.

```tsx
'use client'

import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

export type PriceSeriesPoint = {
  tradeDate: string
  avgPrice: number | null
  ma8?: number | null
  ma26?: number | null
  ma52?: number | null
}

const LINES = [
  { key: 'avgPrice', label: '평균가', color: 'var(--color-ink)', width: 2 },
  { key: 'ma8', label: 'MA8', color: 'var(--color-accent)', width: 1 },
  { key: 'ma26', label: 'MA26', color: 'var(--color-up)', width: 1 },
  { key: 'ma52', label: 'MA52', color: 'var(--color-down)', width: 1 },
] as const

export function PriceChart({ data, height = 320 }: { data: PriceSeriesPoint[]; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
        <CartesianGrid stroke="var(--color-line)" vertical={false} />
        <XAxis
          dataKey="tradeDate"
          tick={{ fontSize: 11, fill: 'var(--color-muted)' }}
          tickLine={false}
          axisLine={false}
          minTickGap={40}
        />
        <YAxis
          tick={{ fontSize: 11, fill: 'var(--color-muted)' }}
          tickLine={false}
          axisLine={false}
          width={64}
          domain={['dataMin - 2000', 'dataMax + 2000']}
          tickFormatter={(value: number) => value.toLocaleString('ko-KR')}
        />
        <Tooltip
          contentStyle={{
            background: 'var(--color-surface)',
            border: '1px solid var(--color-line)',
            borderRadius: 8,
            fontSize: 12,
          }}
          // Recharts 3의 formatter는 ValueType(문자열·배열 가능)을 준다.
          // 명시적 : number 를 쓰면 TS2322가 난다. 좁힌 뒤 유한성을 확인한다.
          // Number(null)은 0이므로 유한성 검사를 빼면 값 없음이 0원으로 보인다.
          formatter={(value, name) => {
            const numeric = typeof value === 'number' ? value : Number(value)
            return [
              Number.isFinite(numeric) ? `${numeric.toLocaleString('ko-KR')}원` : '—',
              name,
            ]
          }}
        />
        {LINES.map((line) => (
          <Line
            key={line.key}
            type="monotone"
            dataKey={line.key}
            name={line.label}
            stroke={line.color}
            strokeWidth={line.width}
            dot={false}
            // 데이터가 부족해 null인 구간은 선을 잇지 않는다.
            connectNulls={false}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  )
}
```

- [ ] **Step 3: 앱 레이아웃과 내비게이션**

`apps/web/components/app-nav.tsx`:

```tsx
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
```

`apps/web/app/(app)/layout.tsx`:

```tsx
import { AppNav } from '@/components/app-nav'

// 이 아래 모든 화면이 DB에서 현재 시세와 보유 현황을 읽는다. Prisma 조회는
// Next의 동적 신호가 아니라서 그냥 두면 빌드 시점 값으로 정적 렌더링되고,
// 배포 후 수집이 돌아도 화면 숫자가 갱신되지 않는다. 가격추적 시스템에서
// 낡은 숫자는 화면이 멀쩡해 보이는 만큼 위험하다.
// 레이아웃의 route segment config는 하위 세그먼트 전체에 적용되므로
// 앞으로 추가할 화면도 자동으로 동적이 된다.
export const dynamic = 'force-dynamic'

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-dvh">
      <AppNav />
      <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
    </div>
  )
}
```

`apps/web/app/page.tsx`를 리다이렉트로 바꾼다.

```tsx
import { redirect } from 'next/navigation'

export default function Home() {
  redirect('/dashboard')
}
```

- [ ] **Step 4: 대시보드 화면**

`apps/web/app/(app)/dashboard/page.tsx`:

```tsx
import { Card, CardTitle } from '@/components/ui/card'
import { Stat } from '@/components/ui/stat'
import { Empty } from '@/components/ui/empty'
import { Badge } from '@/components/ui/badge'
import { PriceChart } from '@/components/charts/price-chart'
import { getMarketHistory, getMarketStats } from '@/lib/queries/market'
import { getActiveTargets, getHoldingsSummary } from '@/lib/queries/company'
import { MA_WINDOWS, movingAverage } from '@/lib/analytics/ma'
import { percentile, priceBand } from '@/lib/analytics/percentile'
import { decisionScore } from '@/lib/analytics/score'
import { valuation } from '@/lib/analytics/valuation'
import { DASH, formatKrw, formatPercent, formatQuantity } from '@/lib/money'
import { resolvePeriod } from '@/lib/period'

export default async function DashboardPage() {
  const [stats, holdings, targets] = await Promise.all([
    getMarketStats(),
    getHoldingsSummary(),
    getActiveTargets(),
  ])

  if (!stats.latest) {
    return (
      <Empty
        title="수집된 REC 시세가 없습니다"
        hint="수집 상태 화면에서 수동 수집을 실행하거나, 수집기가 정상 동작하는지 확인하세요."
      />
    )
  }

  const yearAgo = resolvePeriod('1Y').from
  const history = await getMarketHistory({ from: yearAgo })
  const prices = history.map((point) => point.avgPrice)

  // 이동평균은 한 번만 계산한다. map 안에서 다시 부르면 313일 × 3계열이
  // 매 인덱스마다 재계산되어 O(n²)가 된다.
  const ma8Series = movingAverage(prices, MA_WINDOWS.MA8)
  const ma26Series = movingAverage(prices, MA_WINDOWS.MA26)
  const ma52Series = movingAverage(prices, MA_WINDOWS.MA52)

  const ma8 = ma8Series.at(-1) ?? null
  const ma26 = ma26Series.at(-1) ?? null
  const ma52 = ma52Series.at(-1) ?? null

  const window = prices.filter((price): price is number => price !== null)
  const current = stats.latest.avgPrice
  const percentileValue = current === null ? null : percentile(current, window)
  const band = priceBand(percentileValue)

  const volumes = history.map((point) => point.volume).filter((v): v is number => v !== null)
  const recentVolumes = volumes.slice(-26)
  const averageVolume3m =
    recentVolumes.length > 0
      ? recentVolumes.reduce((sum, value) => sum + value, 0) / recentVolumes.length
      : null

  const score = decisionScore({
    percentile: percentileValue,
    currentPrice: current,
    ma8,
    ma26,
    recentVolume: stats.latest.volume,
    averageVolume3m,
  })

  const evaluated = valuation({ holdings: holdings.holdings, unitPrice: current?.toString() ?? null })

  const chartData = history.map((point, index) => ({
    tradeDate: point.tradeDate,
    avgPrice: point.avgPrice,
    ma8: ma8Series[index],
    ma26: ma26Series[index],
    ma52: ma52Series[index],
  }))

  const changeTone = stats.changeRate === null ? 'neutral' : stats.changeRate >= 0 ? 'up' : 'down'

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">REC 시장</h1>
        <p className="mt-1 text-sm text-[var(--color-muted)]">
          최근 거래일 {stats.latest.tradeDate}
        </p>
      </div>

      <Card>
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="평균가" value={formatKrw(stats.latest.avgPrice)} />
          <Stat label="종가" value={formatKrw(stats.latest.closePrice)} />
          <Stat label="거래량" value={formatQuantity(stats.latest.volume)} sub="REC" />
          <Stat
            label="전 거래일 대비"
            value={formatPercent(stats.changeRate)}
            tone={changeTone}
          />
        </div>
      </Card>

      <Card>
        <CardTitle>최근 1년 가격 추이</CardTitle>
        <div className="mt-4">
          <PriceChart data={chartData} />
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardTitle>보유 REC</CardTitle>
          {holdings.byPlant.length === 0 ? (
            <div className="mt-4">
              <Empty title="등록된 발전소가 없습니다" hint="보유 REC 화면에서 발전소를 먼저 등록하세요." />
            </div>
          ) : (
            <div className="mt-4 grid gap-6 sm:grid-cols-3">
              <Stat label="보유량" value={formatQuantity(holdings.holdings)} sub="REC" />
              <Stat label="현재 평가액" value={formatKrw(evaluated.amount, { compact: true })} />
              <Stat
                label="목표가격"
                value={targets.length === 0 ? DASH : formatKrw(targets[0].targetPrice)}
                sub={targets.length === 0 ? '미설정' : targets[0].name}
              />
            </div>
          )}
        </Card>

        <Card>
          <CardTitle>매각 판단</CardTitle>
          <div className="mt-4 space-y-3">
            <Row
              label="가격 위치"
              value={band?.label ?? DASH}
              detail={percentileValue === null ? '표본 부족' : `상위 ${formatPercent(100 - percentileValue, 0)}`}
              score={score.breakdown.position}
            />
            <Row
              label="추세"
              value={trendLabel(score.breakdown.trend)}
              detail={ma26 === null ? 'MA26 계산 불가' : `MA8 ${formatKrw(ma8)} / MA26 ${formatKrw(ma26)}`}
              score={score.breakdown.trend}
            />
            <Row
              label="거래량"
              value={volumeLabel(score.breakdown.volume)}
              detail={averageVolume3m === null ? '평균 계산 불가' : `3개월 평균 ${formatQuantity(Math.round(averageVolume3m))}`}
              score={score.breakdown.volume}
            />

            <div className="flex items-center justify-between border-t border-[var(--color-line)] pt-3">
              <span className="text-sm font-medium">종합</span>
              <span className="flex items-center gap-2">
                <span className="tabular text-sm text-[var(--color-muted)]">
                  {score.total === null ? DASH : score.total > 0 ? `+${score.total}` : score.total}
                </span>
                <Badge tone={score.total === null ? 'neutral' : score.total >= 2 ? 'up' : score.total <= -2 ? 'down' : 'neutral'}>
                  {score.label}
                </Badge>
              </span>
            </div>

            <p className="text-xs text-[var(--color-muted)]">
              가격 예측이 아니라 내부 매각 의사결정 보조지표입니다. MA52 {formatKrw(ma52)}.
            </p>
          </div>
        </Card>
      </div>
    </div>
  )
}

function Row({
  label,
  value,
  detail,
  score,
}: {
  label: string
  value: string
  detail: string
  score: number | null
}) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <div>
        <p className="text-sm">{label}</p>
        <p className="text-xs text-[var(--color-muted)]">{detail}</p>
      </div>
      <span className="tabular text-sm">
        {value}
        <span className="ml-2 text-[var(--color-muted)]">
          {score === null ? DASH : score > 0 ? `+${score}` : score}
        </span>
      </span>
    </div>
  )
}

function trendLabel(score: number | null): string {
  if (score === null) return DASH
  if (score >= 2) return '상승'
  if (score === 1) return '완만한 상승'
  if (score === 0) return '혼조'
  if (score === -1) return '완만한 하락'
  return '하락'
}

function volumeLabel(score: number | null): string {
  if (score === null) return DASH
  if (score === 1) return '증가'
  if (score === 0) return '보통'
  return '감소'
}
```

- [ ] **Step 5: 실제 데이터로 확인**

```powershell
npm run dev
```

`http://localhost:3000/dashboard`에서 확인한다.

1. 최근 거래일이 2026-08-11 전후로 표시된다
2. 평균가·종가·거래량이 실제 값이다
3. 차트에 1년치 선과 MA8/MA26/MA52가 그려진다
4. 발전소가 없으므로 보유 REC 카드는 빈 상태 안내를 보인다
5. 매각 판단의 세 항목에 점수가 붙고 종합 판정이 나온다

계획 A 데이터가 fixture이므로 값 자체는 의미가 없다. **표시가 되는지, `—`가 나와야 할 곳에만 나오는지**를 본다.

- [ ] **Step 6: 커밋**

```powershell
git add -A
git commit -m "feat(web): 공용 UI와 대시보드 추가

시세 요약, 1년 가격 추이 차트, 보유 REC 평가액, 매각 판단 지표를 한 화면에
모았다. 숫자는 고정폭으로 정렬해 자릿수가 흔들리지 않게 했다.

계산 불가 항목은 대시로 표시하고 사유를 함께 적는다. 차트도
connectNulls를 끄고 결측 구간의 선을 잇지 않는다.

shadcn CLI 대신 프리미티브를 직접 작성했다. 대화형 프롬프트가
자동화 환경에서 멈출 수 있고 필요한 컴포넌트가 6개뿐이다."
```

---

### Task 8: 시장분석 화면

**Files:**
- Create: `apps/web/app/(app)/market/page.tsx`
- Create: `apps/web/components/period-tabs.tsx`
- Create: `apps/web/components/charts/volume-chart.tsx`

**Interfaces:**
- Consumes: Task 6의 `getMarketHistory`, `getMarketStats`, `resolvePeriod`
- Produces: `/market` 화면 (기간 선택, 지표 표, 가격·거래량 차트, 가격 위치)

- [ ] **Step 1: 기간 선택 탭**

`apps/web/components/period-tabs.tsx` — `searchParams`로 상태를 관리해 서버에서 다시 그린다.

```tsx
import Link from 'next/link'
import { PERIOD_KEYS, PERIOD_LABELS, type PeriodKey } from '@/lib/period'

export function PeriodTabs({ current, basePath }: { current: PeriodKey; basePath: string }) {
  return (
    <div className="flex flex-wrap gap-1">
      {PERIOD_KEYS.map((key) => (
        <Link
          key={key}
          href={`${basePath}?period=${key}`}
          className={`rounded-md px-3 py-1.5 text-sm ${
            key === current
              ? 'bg-[var(--color-accent)] text-white'
              : 'border border-[var(--color-line)] text-[var(--color-muted)] hover:text-[var(--color-ink)]'
          }`}
        >
          {PERIOD_LABELS[key]}
        </Link>
      ))}
    </div>
  )
}
```

- [ ] **Step 2: 거래량 차트**

`apps/web/components/charts/volume-chart.tsx`:

```tsx
'use client'

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

export function VolumeChart({
  data,
  height = 200,
}: {
  data: { tradeDate: string; volume: number | null }[]
  height?: number
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
        <CartesianGrid stroke="var(--color-line)" vertical={false} />
        <XAxis
          dataKey="tradeDate"
          tick={{ fontSize: 11, fill: 'var(--color-muted)' }}
          tickLine={false}
          axisLine={false}
          minTickGap={40}
        />
        <YAxis
          tick={{ fontSize: 11, fill: 'var(--color-muted)' }}
          tickLine={false}
          axisLine={false}
          width={64}
          tickFormatter={(value: number) => value.toLocaleString('ko-KR')}
        />
        <Tooltip
          contentStyle={{
            background: 'var(--color-surface)',
            border: '1px solid var(--color-line)',
            borderRadius: 8,
            fontSize: 12,
          }}
          formatter={(value) => {
            const numeric = typeof value === 'number' ? value : Number(value)
            return [
              Number.isFinite(numeric) ? `${numeric.toLocaleString('ko-KR')} REC` : '—',
              '거래량',
            ]
          }}
        />
        <Bar dataKey="volume" fill="var(--color-accent)" isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  )
}
```

- [ ] **Step 3: 시장분석 화면**

`apps/web/app/(app)/market/page.tsx`:

```tsx
import { Card, CardTitle } from '@/components/ui/card'
import { Empty } from '@/components/ui/empty'
import { Table, Td, Th } from '@/components/ui/table'
import { PeriodTabs } from '@/components/period-tabs'
import { PriceChart } from '@/components/charts/price-chart'
import { VolumeChart } from '@/components/charts/volume-chart'
import { getMarketHistory, getMarketStats } from '@/lib/queries/market'
import { MA_WINDOWS, movingAverage } from '@/lib/analytics/ma'
import { percentile, priceBand } from '@/lib/analytics/percentile'
import { DASH, formatKrw, formatPercent, formatQuantity } from '@/lib/money'
import { resolvePeriod } from '@/lib/period'

export default async function MarketPage({
  searchParams,
}: {
  searchParams: Promise<{ period?: string }>
}) {
  const { period } = await searchParams
  const resolved = resolvePeriod(period)

  const [history, stats] = await Promise.all([
    getMarketHistory({ from: resolved.from }),
    getMarketStats(),
  ])

  if (history.length === 0) {
    return <Empty title="해당 기간에 수집된 데이터가 없습니다" hint="다른 기간을 선택해 보세요." />
  }

  const prices = history.map((point) => point.avgPrice)
  const ma8 = movingAverage(prices, MA_WINDOWS.MA8)
  const ma26 = movingAverage(prices, MA_WINDOWS.MA26)
  const ma52 = movingAverage(prices, MA_WINDOWS.MA52)

  const chartData = history.map((point, index) => ({
    tradeDate: point.tradeDate,
    avgPrice: point.avgPrice,
    ma8: ma8[index],
    ma26: ma26[index],
    ma52: ma52[index],
  }))

  const yearWindow = (await getMarketHistory({ from: resolvePeriod('1Y').from }))
    .map((point) => point.avgPrice)
    .filter((price): price is number => price !== null)

  const current = stats.latest?.avgPrice ?? null
  const percentileValue = current === null ? null : percentile(current, yearWindow)
  const band = priceBand(percentileValue)

  const latest = stats.latest

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">시장분석</h1>
          <p className="mt-1 text-sm text-[var(--color-muted)]">
            {history[0].tradeDate} ~ {history[history.length - 1].tradeDate} · 거래일 {history.length}일
          </p>
        </div>
        <PeriodTabs current={resolved.key} basePath="/market" />
      </div>

      <Card>
        <CardTitle>최근 거래일 지표</CardTitle>
        <div className="mt-4">
          <Table>
            <tbody>
              <MetricRow label="평균가" value={formatKrw(latest?.avgPrice)} />
              <MetricRow label="종가" value={formatKrw(latest?.closePrice)} />
              <MetricRow label="최고가" value={formatKrw(latest?.highPrice)} />
              <MetricRow label="최저가" value={formatKrw(latest?.lowPrice)} />
              <MetricRow label="거래량" value={`${formatQuantity(latest?.volume)} REC`} />
              <MetricRow label="거래금액" value={formatKrw(latest?.tradeAmount, { compact: true })} />
              <MetricRow label="직전 거래일 대비" value={formatPercent(stats.changeRate)} />
              <MetricRow label="1개월 평균 대비" value={compare(current, stats.average1m)} />
              <MetricRow label="3개월 평균 대비" value={compare(current, stats.average3m)} />
              <MetricRow label="1년 평균 대비" value={compare(current, stats.average12m)} />
            </tbody>
          </Table>
        </div>
      </Card>

      <Card>
        <CardTitle>가격과 이동평균</CardTitle>
        <div className="mt-4">
          <PriceChart data={chartData} height={360} />
        </div>
        <p className="mt-2 text-xs text-[var(--color-muted)]">
          주 2회 거래이므로 MA8은 약 1개월, MA26은 약 3개월, MA52는 약 6개월에 해당합니다.
        </p>
      </Card>

      <Card>
        <CardTitle>거래량</CardTitle>
        <div className="mt-4">
          <VolumeChart data={history.map((point) => ({ tradeDate: point.tradeDate, volume: point.volume }))} />
        </div>
      </Card>

      <Card>
        <CardTitle>가격 위치</CardTitle>
        <div className="mt-4 grid gap-6 sm:grid-cols-2">
          <div className="space-y-2 text-sm">
            <Line label="현재 REC" value={formatKrw(current)} />
            <Line label="최근 1개월 평균" value={formatKrw(stats.average1m)} />
            <Line label="최근 3개월 평균" value={formatKrw(stats.average3m)} />
            <Line label="최근 1년 평균" value={formatKrw(stats.average12m)} />
          </div>
          <div className="space-y-2 text-sm">
            <Line label="1년 최고" value={formatKrw(stats.high1y)} />
            <Line label="1년 최저" value={formatKrw(stats.low1y)} />
            <Line
              label="현재 Percentile"
              value={percentileValue === null ? DASH : formatPercent(percentileValue, 0)}
            />
            <Line label="가격 위치" value={band?.label ?? DASH} />
          </div>
        </div>
        {percentileValue === null ? (
          <p className="mt-3 text-xs text-[var(--color-muted)]">
            1년 백분위는 거래일 표본이 26일 이상 쌓여야 계산됩니다.
          </p>
        ) : null}
      </Card>
    </div>
  )
}

function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <tr>
      <Th>{label}</Th>
      <Td align="right">{value}</Td>
    </tr>
  )
}

function Line({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4">
      <span className="text-[var(--color-muted)]">{label}</span>
      <span className="tabular">{value}</span>
    </div>
  )
}

function compare(current: number | null, average: number | null): string {
  if (current === null || average === null || average === 0) return DASH
  return formatPercent(((current - average) / average) * 100)
}
```

- [ ] **Step 4: 확인**

```powershell
npm run dev
```

`http://localhost:3000/market`에서 확인한다.

1. 기간 탭 6개가 동작하고 URL이 `?period=3M`처럼 바뀐다
2. `1M`을 고르면 거래일 수가 8~10일로 줄고 MA26·MA52 선이 사라진다 (표본 부족이므로 정상)
3. `ALL`을 고르면 거래일 313일이 나온다
4. 거래량 막대 차트가 그려진다
5. 가격 위치의 Percentile이 값을 낸다

- [ ] **Step 5: 커밋**

```powershell
git add -A
git commit -m "feat(web): 시장분석 화면 추가

기간 선택을 searchParams로 관리해 서버에서 다시 계산한다. 클라이언트
상태를 두지 않아 새로고침과 링크 공유가 그대로 동작한다.

짧은 기간을 고르면 MA26과 MA52 선이 사라지는데 표본 부족이므로
정상이다. 이때 선을 억지로 그리지 않는 것이 이 화면의 요점이다."
```

---

### Task 9: 보유 REC 관리

**Files:**
- Create: `apps/web/app/(app)/inventory/page.tsx`
- Create: `apps/web/app/(app)/inventory/plant-form.tsx`, `inventory-form.tsx`, `sale-form.tsx`
- Create: `apps/web/app/api/plants/route.ts`, `apps/web/app/api/plants/[id]/route.ts`
- Create: `apps/web/app/api/inventory/route.ts`, `apps/web/app/api/inventory/[id]/route.ts`
- Create: `apps/web/app/api/sales/route.ts`
- Create: `apps/web/lib/validate.ts`, `apps/web/lib/validate.test.ts`

**Interfaces:**
- Consumes: Task 6의 `getHoldingsSummary`
- Produces:
  - `parseDecimalField(value: unknown, field: string): { ok: true; value: string } | { ok: false; error: string }`
  - `parseDateField(value: unknown, field: string): { ok: true; value: Date } | { ok: false; error: string }`
  - `/inventory` 화면과 CRUD Route Handler

- [ ] **Step 1: 검증 헬퍼 테스트 작성**

`apps/web/lib/validate.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { parseDateField, parseDecimalField, parsePositiveInt } from './validate'

describe('parseDecimalField', () => {
  it('숫자 문자열을 통과시킨다', () => {
    expect(parseDecimalField('1000.5', '수량')).toEqual({ ok: true, value: '1000.5' })
  })

  it('숫자 타입도 받는다', () => {
    expect(parseDecimalField(1000, '수량')).toEqual({ ok: true, value: '1000' })
  })

  it('음수를 거부한다', () => {
    const result = parseDecimalField('-1', '수량')
    expect(result.ok).toBe(false)
  })

  it('숫자가 아니면 거부하고 필드명을 알려준다', () => {
    const result = parseDecimalField('abc', '단가')
    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.error).toContain('단가')
  })

  it('빈 값을 거부한다', () => {
    expect(parseDecimalField('', '수량').ok).toBe(false)
    expect(parseDecimalField(null, '수량').ok).toBe(false)
  })

  it('0은 허용한다', () => {
    expect(parseDecimalField('0', '수량').ok).toBe(true)
  })
})

describe('parseDateField', () => {
  it('YYYY-MM-DD를 받는다', () => {
    const result = parseDateField('2026-08-06', '발급일')
    expect(result.ok).toBe(true)
    if (result.ok) expect(result.value.toISOString().slice(0, 10)).toBe('2026-08-06')
  })

  it('형식이 틀리면 거부한다', () => {
    expect(parseDateField('2026/08/06', '발급일').ok).toBe(false)
  })

  it('존재하지 않는 날짜를 거부한다', () => {
    expect(parseDateField('2026-02-30', '발급일').ok).toBe(false)
  })
})

describe('parsePositiveInt', () => {
  it('양의 정수를 받는다', () => {
    expect(parsePositiveInt('12', 'id')).toEqual({ ok: true, value: 12 })
  })

  it('0과 음수를 거부한다', () => {
    expect(parsePositiveInt('0', 'id').ok).toBe(false)
    expect(parsePositiveInt('-1', 'id').ok).toBe(false)
  })

  it('소수를 거부한다', () => {
    expect(parsePositiveInt('1.5', 'id').ok).toBe(false)
  })
})
```

- [ ] **Step 2: 테스트 실패 확인 후 `lib/validate.ts` 구현**

```ts
import Decimal from 'decimal.js'

export type ParseResult<T> = { ok: true; value: T } | { ok: false; error: string }

export function parseDecimalField(value: unknown, field: string): ParseResult<string> {
  if (value === null || value === undefined || value === '') {
    return { ok: false, error: `${field}을(를) 입력하세요.` }
  }
  try {
    const decimal = new Decimal(String(value).trim())
    if (!decimal.isFinite()) return { ok: false, error: `${field}이(가) 올바른 숫자가 아닙니다.` }
    if (decimal.isNegative()) return { ok: false, error: `${field}은(는) 0 이상이어야 합니다.` }
    return { ok: true, value: decimal.toString() }
  } catch {
    return { ok: false, error: `${field}이(가) 올바른 숫자가 아닙니다.` }
  }
}

export function parseDateField(value: unknown, field: string): ParseResult<Date> {
  const text = String(value ?? '').trim()
  if (!/^\d{4}-\d{2}-\d{2}$/.test(text)) {
    return { ok: false, error: `${field}은(는) YYYY-MM-DD 형식이어야 합니다.` }
  }
  const date = new Date(`${text}T00:00:00.000Z`)
  // Date는 2026-02-30을 3월 2일로 넘겨버린다. 되돌려 비교해 걸러낸다.
  if (Number.isNaN(date.getTime()) || date.toISOString().slice(0, 10) !== text) {
    return { ok: false, error: `${field}이(가) 존재하지 않는 날짜입니다.` }
  }
  return { ok: true, value: date }
}

export function parsePositiveInt(value: unknown, field: string): ParseResult<number> {
  const text = String(value ?? '').trim()
  if (!/^\d+$/.test(text)) return { ok: false, error: `${field}이(가) 올바르지 않습니다.` }
  const parsed = Number(text)
  if (parsed <= 0) return { ok: false, error: `${field}이(가) 올바르지 않습니다.` }
  return { ok: true, value: parsed }
}
```

- [ ] **Step 3: 테스트 통과 확인**

```powershell
npm run test
```

Expected: 모두 통과

- [ ] **Step 4: 발전소 Route Handler**

`apps/web/app/api/plants/route.ts`:

```ts
import { NextResponse } from 'next/server'
import { prisma } from '@/lib/db'
import { parseDecimalField } from '@/lib/validate'

export async function GET() {
  const plants = await prisma.plant.findMany({ orderBy: { name: 'asc' } })
  return NextResponse.json(
    plants.map((plant) => ({
      id: plant.id,
      name: plant.name,
      location: plant.location,
      capacityKw: plant.capacityKw?.toString() ?? null,
      recWeight: plant.recWeight?.toString() ?? null,
      isActive: plant.isActive,
    })),
  )
}

export async function POST(request: Request) {
  const body = (await request.json().catch(() => null)) as Record<string, unknown> | null
  if (!body) return NextResponse.json({ error: '요청 본문이 올바르지 않습니다.' }, { status: 400 })

  const name = String(body.name ?? '').trim()
  if (name.length === 0) return NextResponse.json({ error: '발전소명을 입력하세요.' }, { status: 400 })

  const capacity = body.capacityKw ? parseDecimalField(body.capacityKw, '설비용량') : null
  if (capacity && !capacity.ok) return NextResponse.json({ error: capacity.error }, { status: 400 })

  const weight = body.recWeight ? parseDecimalField(body.recWeight, 'REC 가중치') : null
  if (weight && !weight.ok) return NextResponse.json({ error: weight.error }, { status: 400 })

  const plant = await prisma.plant.create({
    data: {
      name,
      location: body.location ? String(body.location).trim() : null,
      capacityKw: capacity?.ok ? capacity.value : null,
      recWeight: weight?.ok ? weight.value : null,
    },
  })

  return NextResponse.json({ id: plant.id }, { status: 201 })
}
```

`apps/web/app/api/plants/[id]/route.ts` — Next 16에서 `params`는 Promise다.

```ts
import { NextResponse } from 'next/server'
import { prisma } from '@/lib/db'
import { parsePositiveInt } from '@/lib/validate'

export async function DELETE(_request: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params
  const parsed = parsePositiveInt(id, '발전소 ID')
  if (!parsed.ok) return NextResponse.json({ error: parsed.error }, { status: 400 })

  const [inventoryCount, saleCount] = await Promise.all([
    prisma.recInventory.count({ where: { plantId: parsed.value } }),
    prisma.recSale.count({ where: { plantId: parsed.value } }),
  ])

  // 발급이나 매각 기록이 있으면 지우지 않는다. 지우면 과거 집계가 바뀐다.
  if (inventoryCount > 0 || saleCount > 0) {
    return NextResponse.json(
      { error: '발급 또는 매각 기록이 있어 삭제할 수 없습니다. 비활성으로 바꾸세요.' },
      { status: 409 },
    )
  }

  await prisma.plant.delete({ where: { id: parsed.value } })
  return NextResponse.json({ ok: true })
}

export async function PATCH(request: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params
  const parsed = parsePositiveInt(id, '발전소 ID')
  if (!parsed.ok) return NextResponse.json({ error: parsed.error }, { status: 400 })

  const body = (await request.json().catch(() => null)) as { isActive?: boolean } | null
  if (!body || typeof body.isActive !== 'boolean') {
    return NextResponse.json({ error: 'isActive가 필요합니다.' }, { status: 400 })
  }

  await prisma.plant.update({ where: { id: parsed.value }, data: { isActive: body.isActive } })
  return NextResponse.json({ ok: true })
}
```

- [ ] **Step 5: 발급·매각 Route Handler**

`apps/web/app/api/inventory/route.ts`:

```ts
import { NextResponse } from 'next/server'
import { prisma } from '@/lib/db'
import { parseDateField, parseDecimalField, parsePositiveInt } from '@/lib/validate'

export async function GET() {
  const rows = await prisma.recInventory.findMany({
    orderBy: { issueDate: 'desc' },
    include: { plant: { select: { name: true } } },
  })
  return NextResponse.json(
    rows.map((row) => ({
      id: row.id,
      plantId: row.plantId,
      plantName: row.plant.name,
      issueDate: row.issueDate.toISOString().slice(0, 10),
      recQuantity: row.recQuantity.toString(),
      expiredAt: row.expiredAt?.toISOString().slice(0, 10) ?? null,
      memo: row.memo,
    })),
  )
}

export async function POST(request: Request) {
  const body = (await request.json().catch(() => null)) as Record<string, unknown> | null
  if (!body) return NextResponse.json({ error: '요청 본문이 올바르지 않습니다.' }, { status: 400 })

  const plantId = parsePositiveInt(body.plantId, '발전소')
  if (!plantId.ok) return NextResponse.json({ error: plantId.error }, { status: 400 })

  const issueDate = parseDateField(body.issueDate, '발급일')
  if (!issueDate.ok) return NextResponse.json({ error: issueDate.error }, { status: 400 })

  const quantity = parseDecimalField(body.recQuantity, '발급 REC')
  if (!quantity.ok) return NextResponse.json({ error: quantity.error }, { status: 400 })

  const created = await prisma.recInventory.create({
    data: {
      plantId: plantId.value,
      issueDate: issueDate.value,
      recQuantity: quantity.value,
      memo: body.memo ? String(body.memo).trim() : null,
    },
  })

  return NextResponse.json({ id: created.id }, { status: 201 })
}
```

`apps/web/app/api/inventory/[id]/route.ts`:

```ts
import { NextResponse } from 'next/server'
import { prisma } from '@/lib/db'
import { parsePositiveInt } from '@/lib/validate'

export async function DELETE(_request: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params
  const parsed = parsePositiveInt(id, '발급 ID')
  if (!parsed.ok) return NextResponse.json({ error: parsed.error }, { status: 400 })

  await prisma.recInventory.delete({ where: { id: parsed.value } })
  return NextResponse.json({ ok: true })
}
```

`apps/web/app/api/sales/route.ts` — **매각 수량이 보유량을 넘지 않는지 확인한다.** 넘으면 보유량이 음수가 되어 평가액이 마이너스로 표시된다.

```ts
import Decimal from 'decimal.js'
import { NextResponse } from 'next/server'
import { prisma } from '@/lib/db'
import { parseDateField, parseDecimalField, parsePositiveInt } from '@/lib/validate'

export async function GET() {
  const rows = await prisma.recSale.findMany({
    orderBy: { saleDate: 'desc' },
    include: { plant: { select: { name: true } } },
  })
  return NextResponse.json(
    rows.map((row) => ({
      id: row.id,
      plantId: row.plantId,
      plantName: row.plant.name,
      saleDate: row.saleDate.toISOString().slice(0, 10),
      quantity: row.quantity.toString(),
      unitPrice: row.unitPrice.toString(),
      saleAmount: row.saleAmount.toString(),
      buyer: row.buyer,
    })),
  )
}

export async function POST(request: Request) {
  const body = (await request.json().catch(() => null)) as Record<string, unknown> | null
  if (!body) return NextResponse.json({ error: '요청 본문이 올바르지 않습니다.' }, { status: 400 })

  const plantId = parsePositiveInt(body.plantId, '발전소')
  if (!plantId.ok) return NextResponse.json({ error: plantId.error }, { status: 400 })

  const saleDate = parseDateField(body.saleDate, '매각일')
  if (!saleDate.ok) return NextResponse.json({ error: saleDate.error }, { status: 400 })

  const quantity = parseDecimalField(body.quantity, '매각 수량')
  if (!quantity.ok) return NextResponse.json({ error: quantity.error }, { status: 400 })

  const unitPrice = parseDecimalField(body.unitPrice, '단가')
  if (!unitPrice.ok) return NextResponse.json({ error: unitPrice.error }, { status: 400 })

  const [issuedAgg, soldAgg] = await Promise.all([
    prisma.recInventory.aggregate({
      where: { plantId: plantId.value, expiredAt: null },
      _sum: { recQuantity: true },
    }),
    prisma.recSale.aggregate({ where: { plantId: plantId.value }, _sum: { quantity: true } }),
  ])

  const issued = new Decimal(issuedAgg._sum.recQuantity?.toString() ?? '0')
  const sold = new Decimal(soldAgg._sum.quantity?.toString() ?? '0')
  const available = issued.minus(sold)
  const requested = new Decimal(quantity.value)

  if (requested.gt(available)) {
    return NextResponse.json(
      { error: `보유량(${available.toString()} REC)보다 많이 매각할 수 없습니다.` },
      { status: 409 },
    )
  }

  const amount = body.saleAmount
    ? parseDecimalField(body.saleAmount, '매각금액')
    : { ok: true as const, value: requested.mul(new Decimal(unitPrice.value)).toString() }
  if (!amount.ok) return NextResponse.json({ error: amount.error }, { status: 400 })

  const created = await prisma.recSale.create({
    data: {
      plantId: plantId.value,
      saleDate: saleDate.value,
      quantity: quantity.value,
      unitPrice: unitPrice.value,
      saleAmount: amount.value,
      buyer: body.buyer ? String(body.buyer).trim() : null,
      memo: body.memo ? String(body.memo).trim() : null,
    },
  })

  return NextResponse.json({ id: created.id }, { status: 201 })
}
```

- [ ] **Step 6: 보유 REC 화면**

`apps/web/app/(app)/inventory/page.tsx` — 발전소·발급·매각 세 섹션과 발전소별 집계 표를 둔다.

```tsx
import { Card, CardTitle } from '@/components/ui/card'
import { Empty } from '@/components/ui/empty'
import { Table, Td, Th } from '@/components/ui/table'
import { Stat } from '@/components/ui/stat'
import { PlantForm } from './plant-form'
import { InventoryForm } from './inventory-form'
import { SaleForm } from './sale-form'
import { prisma } from '@/lib/db'
import { getHoldingsSummary } from '@/lib/queries/company'
import { getLatestMarket } from '@/lib/queries/market'
import { valuation } from '@/lib/analytics/valuation'
import { formatKrw, formatQuantity } from '@/lib/money'

export default async function InventoryPage() {
  const [summary, latest, plants] = await Promise.all([
    getHoldingsSummary(),
    getLatestMarket(),
    prisma.plant.findMany({ orderBy: { name: 'asc' }, select: { id: true, name: true } }),
  ])

  const unitPrice = latest?.avgPrice?.toString() ?? null

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold tracking-tight">보유 REC</h1>

      <Card>
        <div className="grid gap-6 sm:grid-cols-4">
          <Stat label="총 발급" value={formatQuantity(summary.issued)} sub="REC" />
          <Stat label="총 매각" value={formatQuantity(summary.sold)} sub="REC" />
          <Stat label="현재 보유" value={formatQuantity(summary.holdings)} sub="REC" />
          <Stat
            label="현재 평가액"
            value={formatKrw(valuation({ holdings: summary.holdings, unitPrice }).amount, { compact: true })}
            sub={latest ? `${latest.tradeDate} 평균가 기준` : null}
          />
        </div>
      </Card>

      <Card>
        <CardTitle>발전소별</CardTitle>
        {summary.byPlant.length === 0 ? (
          <div className="mt-4">
            <Empty title="등록된 발전소가 없습니다" hint="아래에서 발전소를 먼저 등록하세요." />
          </div>
        ) : (
          <div className="mt-4">
            <Table>
              <thead>
                <tr>
                  <Th>발전소</Th>
                  <Th align="right">발급</Th>
                  <Th align="right">매각</Th>
                  <Th align="right">보유</Th>
                  <Th align="right">평가액</Th>
                </tr>
              </thead>
              <tbody>
                {summary.byPlant.map((plant) => (
                  <tr key={plant.plantId}>
                    <Td>{plant.plantName}</Td>
                    <Td align="right">{formatQuantity(plant.issued)}</Td>
                    <Td align="right">{formatQuantity(plant.sold)}</Td>
                    <Td align="right">{formatQuantity(plant.holdings)}</Td>
                    <Td align="right">
                      {formatKrw(valuation({ holdings: plant.holdings, unitPrice }).amount, { compact: true })}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>
        )}
      </Card>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card>
          <CardTitle>발전소 등록</CardTitle>
          <PlantForm />
        </Card>
        <Card>
          <CardTitle>REC 발급 등록</CardTitle>
          <InventoryForm plants={plants} />
        </Card>
        <Card>
          <CardTitle>매각 등록</CardTitle>
          <SaleForm plants={plants} />
        </Card>
      </div>
    </div>
  )
}
```

- [ ] **Step 7: 폼 컴포넌트 3개 작성**

세 폼은 구조가 같다. `'use client'`로 두고, `fetch` 후 성공하면 `router.refresh()`로 서버 컴포넌트를 다시 그린다. 실패하면 서버가 준 `error` 문자열을 그대로 보여준다.

`apps/web/app/(app)/inventory/plant-form.tsx`:

```tsx
'use client'

import { useRouter } from 'next/navigation'
import { useState, type FormEvent } from 'react'
import { Button } from '@/components/ui/button'

export function PlantForm() {
  const router = useRouter()
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setPending(true)
    setError(null)

    const form = event.currentTarget
    const data = Object.fromEntries(new FormData(form).entries())

    const response = await fetch('/api/plants', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(data),
    })

    if (response.ok) {
      form.reset()
      router.refresh()
    } else {
      const payload = (await response.json().catch(() => ({}))) as { error?: string }
      setError(payload.error ?? '등록에 실패했습니다.')
    }
    setPending(false)
  }

  return (
    <form onSubmit={onSubmit} className="mt-4 space-y-3">
      <Field name="name" label="발전소명" required />
      <Field name="location" label="위치" />
      <Field name="capacityKw" label="설비용량 (kW)" type="number" step="0.01" />
      <Field name="recWeight" label="REC 가중치 (참고용)" type="number" step="0.01" />
      {error ? <p className="text-sm text-[var(--color-up)]">{error}</p> : null}
      <Button type="submit" disabled={pending}>
        {pending ? '등록 중…' : '등록'}
      </Button>
    </form>
  )
}

export function Field({
  name,
  label,
  type = 'text',
  required = false,
  step,
  options,
}: {
  name: string
  label: string
  type?: string
  required?: boolean
  step?: string
  options?: { value: string | number; label: string }[]
}) {
  const className =
    'mt-1 w-full rounded-md border border-[var(--color-line)] bg-[var(--color-canvas)] px-2.5 py-1.5 text-sm outline-none focus:border-[var(--color-accent)]'

  return (
    <label className="block text-sm">
      <span className="text-[var(--color-muted)]">{label}</span>
      {options ? (
        <select name={name} required={required} className={className}>
          <option value="">선택하세요</option>
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      ) : (
        <input name={name} type={type} step={step} required={required} className={className} />
      )}
    </label>
  )
}
```

`apps/web/app/(app)/inventory/inventory-form.tsx`:

```tsx
'use client'

import { useRouter } from 'next/navigation'
import { useState, type FormEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Field } from './plant-form'

export function InventoryForm({ plants }: { plants: { id: number; name: string }[] }) {
  const router = useRouter()
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setPending(true)
    setError(null)

    const form = event.currentTarget
    const data = Object.fromEntries(new FormData(form).entries())

    const response = await fetch('/api/inventory', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(data),
    })

    if (response.ok) {
      form.reset()
      router.refresh()
    } else {
      const payload = (await response.json().catch(() => ({}))) as { error?: string }
      setError(payload.error ?? '등록에 실패했습니다.')
    }
    setPending(false)
  }

  if (plants.length === 0) {
    return <p className="mt-4 text-sm text-[var(--color-muted)]">발전소를 먼저 등록하세요.</p>
  }

  return (
    <form onSubmit={onSubmit} className="mt-4 space-y-3">
      <Field
        name="plantId"
        label="발전소"
        required
        options={plants.map((plant) => ({ value: plant.id, label: plant.name }))}
      />
      <Field name="issueDate" label="발급일" type="date" required />
      <Field name="recQuantity" label="발급 REC (가중치 적용 수량)" type="number" step="0.01" required />
      <Field name="memo" label="메모" />
      {error ? <p className="text-sm text-[var(--color-up)]">{error}</p> : null}
      <Button type="submit" disabled={pending}>
        {pending ? '등록 중…' : '등록'}
      </Button>
    </form>
  )
}
```

`apps/web/app/(app)/inventory/sale-form.tsx` — 위와 동일한 구조이며 필드와 엔드포인트만 다르다. 보유량 초과 시 서버가 409와 메시지를 주므로 그대로 표시된다.

```tsx
'use client'

import { useRouter } from 'next/navigation'
import { useState, type FormEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Field } from './plant-form'

export function SaleForm({ plants }: { plants: { id: number; name: string }[] }) {
  const router = useRouter()
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setPending(true)
    setError(null)

    const form = event.currentTarget
    const data = Object.fromEntries(new FormData(form).entries())

    const response = await fetch('/api/sales', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(data),
    })

    if (response.ok) {
      form.reset()
      router.refresh()
    } else {
      const payload = (await response.json().catch(() => ({}))) as { error?: string }
      setError(payload.error ?? '등록에 실패했습니다.')
    }
    setPending(false)
  }

  if (plants.length === 0) {
    return <p className="mt-4 text-sm text-[var(--color-muted)]">발전소를 먼저 등록하세요.</p>
  }

  return (
    <form onSubmit={onSubmit} className="mt-4 space-y-3">
      <Field
        name="plantId"
        label="발전소"
        required
        options={plants.map((plant) => ({ value: plant.id, label: plant.name }))}
      />
      <Field name="saleDate" label="매각일" type="date" required />
      <Field name="quantity" label="매각 수량" type="number" step="0.01" required />
      <Field name="unitPrice" label="단가 (원)" type="number" step="0.01" required />
      <Field name="buyer" label="매수자" />
      {error ? <p className="text-sm text-[var(--color-up)]">{error}</p> : null}
      <Button type="submit" disabled={pending}>
        {pending ? '등록 중…' : '등록'}
      </Button>
    </form>
  )
}
```

- [ ] **Step 8: 실제로 등록해 확인**

```powershell
npm run dev
```

`http://localhost:3000/inventory`에서 순서대로 한다.

1. 발전소 `발전소 A` 등록 → 표에 나타난다
2. 발급 `2026-01-15 / 5000 REC` 등록 → 발급 5,000 / 보유 5,000
3. 매각 `2026-03-10 / 2000 REC / 72000원` 등록 → 매각 2,000 / 보유 3,000
4. **매각 `9999 REC` 시도 → 409와 "보유량(3000 REC)보다 많이 매각할 수 없습니다."**
5. 평가액이 보유량 × 최근 평균가로 계산된다
6. 기록이 있는 발전소 삭제 시도 → 409

4번이 이 화면의 핵심 검증이다. 보유량이 음수가 되면 평가액이 마이너스로 표시된다.

- [ ] **Step 9: 확인용 데이터 정리**

```powershell
docker exec recflow-db psql -U recflow -d recflow -c "DELETE FROM rec_sales; DELETE FROM rec_inventory; DELETE FROM plants;"
```

- [ ] **Step 10: 커밋**

```powershell
git add -A
git commit -m "feat(web): 보유 REC 관리 추가

발전소, 발급, 매각을 등록하고 발전소별 보유량과 평가액을 집계한다.
보유량은 저장하지 않고 발급에서 매각을 빼서 계산한다.

매각 수량이 보유량을 넘으면 409로 거절한다. 넘으면 보유량이 음수가 되어
평가액이 마이너스로 표시된다. 발급이나 매각 기록이 있는 발전소는
삭제하지 않고 비활성으로만 바꾼다. 지우면 과거 집계가 바뀐다."
```

---

### Task 10: 매각 시뮬레이션 화면

**Files:**
- Create: `apps/web/app/(app)/simulation/page.tsx`
- Create: `apps/web/app/(app)/simulation/simulation-panel.tsx`
- Create: `apps/web/app/api/simulation/route.ts`

**Interfaces:**
- Consumes: Task 4의 `simulate`, `simulateTranches`
- Produces: `/simulation` 화면, `POST /api/simulation`

- [ ] **Step 1: 시뮬레이션 Route Handler**

`apps/web/app/api/simulation/route.ts`:

```ts
import { NextResponse } from 'next/server'
import { simulate, simulateTranches } from '@/lib/analytics/simulation'
import { parseDecimalField } from '@/lib/validate'

export async function POST(request: Request) {
  const body = (await request.json().catch(() => null)) as Record<string, unknown> | null
  if (!body) return NextResponse.json({ error: '요청 본문이 올바르지 않습니다.' }, { status: 400 })

  if (body.mode === 'tranches') {
    const raw = Array.isArray(body.tranches) ? body.tranches : []
    const tranches: { quantity: string; price: string }[] = []

    for (const [index, item] of raw.entries()) {
      const entry = item as Record<string, unknown>
      const quantity = parseDecimalField(entry.quantity, `${index + 1}차 수량`)
      if (!quantity.ok) return NextResponse.json({ error: quantity.error }, { status: 400 })
      const price = parseDecimalField(entry.price, `${index + 1}차 가격`)
      if (!price.ok) return NextResponse.json({ error: price.error }, { status: 400 })
      tranches.push({ quantity: quantity.value, price: price.value })
    }

    return NextResponse.json(simulateTranches(tranches))
  }

  const quantity = parseDecimalField(body.quantity, '보유량')
  if (!quantity.ok) return NextResponse.json({ error: quantity.error }, { status: 400 })

  const prices = Array.isArray(body.prices) ? body.prices.map((price) => String(price)) : []
  const currentPrice = body.currentPrice === null || body.currentPrice === undefined
    ? null
    : String(body.currentPrice)

  return NextResponse.json({ rows: simulate({ quantity: quantity.value, prices, currentPrice }) })
}
```

- [ ] **Step 2: 시뮬레이션 화면 (서버)**

`apps/web/app/(app)/simulation/page.tsx`:

```tsx
import { Card } from '@/components/ui/card'
import { Empty } from '@/components/ui/empty'
import { SimulationPanel } from './simulation-panel'
import { getHoldingsSummary } from '@/lib/queries/company'
import { getLatestMarket } from '@/lib/queries/market'

export default async function SimulationPage() {
  const [summary, latest] = await Promise.all([getHoldingsSummary(), getLatestMarket()])

  if (summary.holdings === '0') {
    return (
      <Empty
        title="보유 중인 REC가 없습니다"
        hint="보유 REC 화면에서 발전소와 발급 내역을 먼저 등록하세요."
      />
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">매각 시뮬레이션</h1>
        <p className="mt-1 text-sm text-[var(--color-muted)]">
          보유 {summary.holdings} REC
          {latest?.avgPrice ? ` · 현재가 ${latest.avgPrice.toLocaleString('ko-KR')}원` : ''}
        </p>
      </div>
      <Card>
        <SimulationPanel
          holdings={summary.holdings}
          currentPrice={latest?.avgPrice?.toString() ?? null}
        />
      </Card>
    </div>
  )
}
```

- [ ] **Step 3: 시뮬레이션 패널 (클라이언트)**

`apps/web/app/(app)/simulation/simulation-panel.tsx`:

```tsx
'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Table, Td, Th } from '@/components/ui/table'
import { DASH, formatKrw, formatQuantity } from '@/lib/money'

type SimulationRow = { price: string; revenue: string; deltaFromCurrent: string | null }
type TrancheResult = {
  totalQuantity: string
  totalRevenue: string
  averagePrice: string | null
  rows: { quantity: string; price: string; revenue: string }[]
}

/** 현재가 기준 ±5%를 5단계로 나눈 기본 제안값. 현재가가 없으면 빈 값이다. */
function defaultPrices(currentPrice: string | null): string {
  if (currentPrice === null) return ''
  const base = Number(currentPrice)
  if (!Number.isFinite(base)) return ''
  return [-0.05, -0.025, 0, 0.025, 0.05]
    .map((ratio) => Math.round((base * (1 + ratio)) / 100) * 100)
    .join(', ')
}

export function SimulationPanel({
  holdings,
  currentPrice,
}: {
  holdings: string
  currentPrice: string | null
}) {
  const [mode, setMode] = useState<'full' | 'tranches'>('full')
  const [quantity, setQuantity] = useState(holdings)
  const [priceText, setPriceText] = useState(defaultPrices(currentPrice))
  const [rows, setRows] = useState<SimulationRow[] | null>(null)

  const [tranches, setTranches] = useState([
    { quantity: '', price: '' },
    { quantity: '', price: '' },
  ])
  const [trancheResult, setTrancheResult] = useState<TrancheResult | null>(null)

  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  async function post(body: unknown) {
    setPending(true)
    setError(null)
    const response = await fetch('/api/simulation', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    })
    const payload = await response.json().catch(() => ({}))
    setPending(false)
    if (!response.ok) {
      setError((payload as { error?: string }).error ?? '계산에 실패했습니다.')
      return null
    }
    return payload
  }

  async function runFull() {
    const prices = priceText
      .split(',')
      .map((value) => value.trim())
      .filter((value) => value.length > 0)
    const result = await post({ quantity, prices, currentPrice })
    if (result) setRows((result as { rows: SimulationRow[] }).rows)
  }

  async function runTranches() {
    const result = await post({ mode: 'tranches', tranches })
    if (result) setTrancheResult(result as TrancheResult)
  }

  const trancheTotal = tranches.reduce((sum, row) => sum + (Number(row.quantity) || 0), 0)
  const overHoldings = trancheTotal > Number(holdings)

  const inputClass =
    'w-full rounded-md border border-[var(--color-line)] bg-[var(--color-canvas)] px-2.5 py-1.5 text-sm tabular outline-none focus:border-[var(--color-accent)]'

  return (
    <div>
      <div className="flex gap-1">
        {(['full', 'tranches'] as const).map((key) => (
          <button
            key={key}
            type="button"
            onClick={() => setMode(key)}
            className={`rounded-md px-3 py-1.5 text-sm ${
              mode === key
                ? 'bg-[var(--color-accent)] text-white'
                : 'border border-[var(--color-line)] text-[var(--color-muted)]'
            }`}
          >
            {key === 'full' ? '전량 매각' : '분할 매각'}
          </button>
        ))}
      </div>

      {error ? <p className="mt-4 text-sm text-[var(--color-up)]">{error}</p> : null}

      {mode === 'full' ? (
        <div className="mt-5 space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block text-sm">
              <span className="text-[var(--color-muted)]">매각 수량 (REC)</span>
              <input
                value={quantity}
                onChange={(event) => setQuantity(event.target.value)}
                className={`mt-1 ${inputClass}`}
              />
            </label>
            <label className="block text-sm">
              <span className="text-[var(--color-muted)]">검토 가격 (쉼표로 구분)</span>
              <input
                value={priceText}
                onChange={(event) => setPriceText(event.target.value)}
                className={`mt-1 ${inputClass}`}
              />
            </label>
          </div>

          <Button type="button" onClick={runFull} disabled={pending}>
            {pending ? '계산 중…' : '계산'}
          </Button>

          {rows ? (
            <Table>
              <thead>
                <tr>
                  <Th align="right">가격</Th>
                  <Th align="right">예상 매출</Th>
                  <Th align="right">현재가 대비</Th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const delta = row.deltaFromCurrent
                  const tone =
                    delta === null
                      ? ''
                      : delta.startsWith('-')
                        ? 'text-[var(--color-down)]'
                        : 'text-[var(--color-up)]'
                  return (
                    <tr key={row.price}>
                      <Td align="right">{formatKrw(row.price)}</Td>
                      <Td align="right">{formatKrw(row.revenue)}</Td>
                      <Td align="right">
                        <span className={tone}>
                          {delta === null ? DASH : formatKrw(delta)}
                        </span>
                      </Td>
                    </tr>
                  )
                })}
              </tbody>
            </Table>
          ) : null}
        </div>
      ) : (
        <div className="mt-5 space-y-4">
          <div className="space-y-2">
            {tranches.map((tranche, index) => (
              <div key={index} className="flex items-end gap-2">
                <label className="flex-1 text-sm">
                  <span className="text-[var(--color-muted)]">{index + 1}차 수량</span>
                  <input
                    value={tranche.quantity}
                    onChange={(event) =>
                      setTranches((prev) =>
                        prev.map((row, i) => (i === index ? { ...row, quantity: event.target.value } : row)),
                      )
                    }
                    className={`mt-1 ${inputClass}`}
                  />
                </label>
                <label className="flex-1 text-sm">
                  <span className="text-[var(--color-muted)]">{index + 1}차 가격</span>
                  <input
                    value={tranche.price}
                    onChange={(event) =>
                      setTranches((prev) =>
                        prev.map((row, i) => (i === index ? { ...row, price: event.target.value } : row)),
                      )
                    }
                    className={`mt-1 ${inputClass}`}
                  />
                </label>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setTranches((prev) => prev.filter((_, i) => i !== index))}
                  disabled={tranches.length <= 1}
                >
                  삭제
                </Button>
              </div>
            ))}
          </div>

          <div className="flex gap-2">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setTranches((prev) => [...prev, { quantity: '', price: '' }])}
            >
              회차 추가
            </Button>
            <Button type="button" onClick={runTranches} disabled={pending}>
              {pending ? '계산 중…' : '계산'}
            </Button>
          </div>

          {overHoldings ? (
            <p className="text-sm text-[var(--color-up)]">
              회차 수량 합계 {formatQuantity(trancheTotal)} REC가 보유량 {formatQuantity(holdings)} REC를
              넘습니다. 계획 단계이므로 계산은 가능합니다.
            </p>
          ) : null}

          {trancheResult ? (
            <div className="space-y-4">
              <Table>
                <thead>
                  <tr>
                    <Th>회차</Th>
                    <Th align="right">수량</Th>
                    <Th align="right">가격</Th>
                    <Th align="right">매출</Th>
                  </tr>
                </thead>
                <tbody>
                  {trancheResult.rows.map((row, index) => (
                    <tr key={index}>
                      <Td>{index + 1}차</Td>
                      <Td align="right">{formatQuantity(row.quantity)}</Td>
                      <Td align="right">{formatKrw(row.price)}</Td>
                      <Td align="right">{formatKrw(row.revenue)}</Td>
                    </tr>
                  ))}
                </tbody>
              </Table>

              <div className="grid gap-6 sm:grid-cols-3 border-t border-[var(--color-line)] pt-4">
                <div>
                  <p className="text-sm text-[var(--color-muted)]">총 매각량</p>
                  <p className="tabular mt-1 text-xl font-semibold">
                    {formatQuantity(trancheResult.totalQuantity)} REC
                  </p>
                </div>
                <div>
                  <p className="text-sm text-[var(--color-muted)]">총 예상매출</p>
                  <p className="tabular mt-1 text-xl font-semibold">
                    {formatKrw(trancheResult.totalRevenue)}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-[var(--color-muted)]">평균 매도가 (가중)</p>
                  <p className="tabular mt-1 text-xl font-semibold">
                    {formatKrw(trancheResult.averagePrice)}
                  </p>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: 확인**

발전소·발급을 다시 등록한 뒤 `http://localhost:3000/simulation`에서 확인한다.

1. 전량 매각에서 가격 5단계 표가 나온다
2. 현재가보다 높은 행은 증감이 양수(빨강), 낮은 행은 음수(파랑)
3. 분할 매각에서 3회차를 `3000×72000`, `3000×75000`, `4000×78000`으로 넣으면
   총 매출 `753,000,000원`, 평균 매도가 `75,300원`이 나온다
4. 회차 합계가 보유량을 넘으면 경고가 보인다

3번의 75,300원이 산술평균 75,000원과 다른 것이 핵심이다. 75,000원이 나오면 가중평균이 아니라 산술평균을 쓴 것이다.

- [ ] **Step 5: 커밋**

```powershell
git add -A
git commit -m "feat(web): 매각 시뮬레이션 화면 추가

전량 매각은 목표가별 예상매출과 현재가 대비 증감을, 분할 매각은
회차별 매출과 수량 가중평균 매도가를 보여준다.

평균 매도가는 산술평균이 아니라 가중평균이다. 회차별 수량이 다르면
두 값이 달라지고 가중평균이 실제 실현 단가다."
```

---

### Task 11: 목표가격과 수집 상태

**Files:**
- Create: `apps/web/app/(app)/settings/page.tsx`, `target-form.tsx`
- Create: `apps/web/app/api/targets/route.ts`, `apps/web/app/api/targets/[id]/route.ts`
- Create: `apps/web/app/(app)/admin/page.tsx`, `collect-button.tsx`
- Create: `apps/web/app/api/admin/status/route.ts`, `apps/web/app/api/admin/collect/route.ts`
- Create: `apps/web/lib/queries/collection.ts`
- Modify: `README.md`

**Interfaces:**
- Consumes: `COLLECTOR_INTERNAL_URL`, `collection_runs` 테이블
- Produces: `/settings`, `/admin` 화면

- [ ] **Step 1: 목표가격 Route Handler**

`apps/web/app/api/targets/route.ts`:

```ts
import { NextResponse } from 'next/server'
import { prisma } from '@/lib/db'
import { parseDecimalField } from '@/lib/validate'

export async function GET() {
  const targets = await prisma.priceTarget.findMany({ orderBy: { targetPrice: 'asc' } })
  return NextResponse.json(
    targets.map((target) => ({
      id: target.id,
      name: target.name,
      targetPrice: target.targetPrice.toString(),
      isActive: target.isActive,
    })),
  )
}

export async function POST(request: Request) {
  const body = (await request.json().catch(() => null)) as Record<string, unknown> | null
  if (!body) return NextResponse.json({ error: '요청 본문이 올바르지 않습니다.' }, { status: 400 })

  const name = String(body.name ?? '').trim()
  if (name.length === 0) return NextResponse.json({ error: '이름을 입력하세요.' }, { status: 400 })

  const price = parseDecimalField(body.targetPrice, '목표가격')
  if (!price.ok) return NextResponse.json({ error: price.error }, { status: 400 })

  const created = await prisma.priceTarget.create({
    data: { name, targetPrice: price.value },
  })
  return NextResponse.json({ id: created.id }, { status: 201 })
}
```

`apps/web/app/api/targets/[id]/route.ts`는 `DELETE`(삭제)와 `PATCH`(`isActive` 토글)를 제공한다. 구조는 `app/api/plants/[id]/route.ts`와 같고 `params`가 Promise인 점도 같다.

- [ ] **Step 2: 목표가격 화면**

`apps/web/app/(app)/settings/page.tsx`:

```tsx
import Decimal from 'decimal.js'
import { Card, CardTitle } from '@/components/ui/card'
import { Empty } from '@/components/ui/empty'
import { Badge } from '@/components/ui/badge'
import { Table, Td, Th } from '@/components/ui/table'
import { TargetForm } from './target-form'
import { prisma } from '@/lib/db'
import { getLatestMarket } from '@/lib/queries/market'
import { DASH, formatKrw } from '@/lib/money'

export default async function SettingsPage() {
  const [targets, latest] = await Promise.all([
    prisma.priceTarget.findMany({ orderBy: { targetPrice: 'asc' } }),
    getLatestMarket(),
  ])

  const current = latest?.avgPrice ?? null

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">목표가격</h1>
        <p className="mt-1 text-sm text-[var(--color-muted)]">
          {current === null ? '현재가 없음' : `현재가 ${formatKrw(current)}`}
        </p>
      </div>

      <Card>
        <CardTitle>등록된 목표가격</CardTitle>
        {targets.length === 0 ? (
          <div className="mt-4">
            <Empty
              title="설정된 목표가격이 없습니다"
              hint="매각을 검토할 가격을 등록하면 대시보드와 시뮬레이션에서 기준으로 쓰입니다."
            />
          </div>
        ) : (
          <div className="mt-4">
            <Table>
              <thead>
                <tr>
                  <Th>이름</Th>
                  <Th align="right">목표가격</Th>
                  <Th align="right">현재가 대비</Th>
                  <Th align="right">상태</Th>
                </tr>
              </thead>
              <tbody>
                {targets.map((target) => {
                  const price = new Decimal(target.targetPrice.toString())
                  const reached = current !== null && new Decimal(current).gte(price)
                  const remaining =
                    current === null ? null : price.minus(new Decimal(current)).toString()

                  return (
                    <tr key={target.id}>
                      <Td>{target.name}</Td>
                      <Td align="right">{formatKrw(price.toString())}</Td>
                      <Td align="right">
                        {remaining === null ? DASH : reached ? '달성' : `${formatKrw(remaining)} 남음`}
                      </Td>
                      <Td align="right">
                        <Badge tone={reached ? 'up' : 'neutral'}>
                          {!target.isActive ? '비활성' : reached ? '도달' : '대기'}
                        </Badge>
                      </Td>
                    </tr>
                  )
                })}
              </tbody>
            </Table>
          </div>
        )}
      </Card>

      <Card>
        <CardTitle>목표가격 등록</CardTitle>
        <TargetForm />
      </Card>
    </div>
  )
}
```

`apps/web/app/(app)/settings/target-form.tsx`는 `PlantForm`과 동일한 구조이며, `Field`를 `@/app/(app)/inventory/plant-form`에서 import한다. 필드는 `name`(text, required)과 `targetPrice`(number, step 0.01, required) 두 개이고 POST 대상은 `/api/targets`다.

- [ ] **Step 3: 수집 상태 조회**

`apps/web/lib/queries/collection.ts`:

```ts
import { prisma } from '@/lib/db'

export type CollectionRunView = {
  id: number
  jobType: string
  targetDate: string | null
  status: string
  rowsUpserted: number
  errorMessage: string | null
  startedAt: string
  finishedAt: string | null
}

export async function getRecentRuns(limit = 20): Promise<CollectionRunView[]> {
  const runs = await prisma.collectionRun.findMany({
    orderBy: { startedAt: 'desc' },
    take: limit,
  })
  return runs.map((run) => ({
    id: run.id,
    jobType: run.jobType,
    targetDate: run.targetDate?.toISOString().slice(0, 10) ?? null,
    status: run.status,
    rowsUpserted: run.rowsUpserted,
    errorMessage: run.errorMessage,
    startedAt: run.startedAt.toISOString(),
    finishedAt: run.finishedAt?.toISOString() ?? null,
  }))
}

export async function getCollectionSummary() {
  const [lastSuccess, failureCount, marketCount] = await Promise.all([
    prisma.collectionRun.findFirst({
      where: { status: 'SUCCESS' },
      orderBy: { finishedAt: 'desc' },
    }),
    prisma.collectionRun.count({ where: { status: 'FAILED' } }),
    prisma.recMarket.count(),
  ])

  return {
    lastSuccessAt: lastSuccess?.finishedAt?.toISOString() ?? null,
    lastSuccessDate: lastSuccess?.targetDate?.toISOString().slice(0, 10) ?? null,
    failureCount,
    marketCount,
  }
}
```

- [ ] **Step 4: 관리자 API**

`apps/web/app/api/admin/status/route.ts` — DB 요약과 수집기 `/health`를 함께 돌려준다. 수집기가 죽어 있어도 화면 전체가 죽지 않도록 실패를 흡수한다.

```ts
import { NextResponse } from 'next/server'
import { getCollectionSummary } from '@/lib/queries/collection'

export async function GET() {
  const summary = await getCollectionSummary()

  let collector: unknown = null
  let collectorError: string | null = null

  try {
    const base = process.env.COLLECTOR_INTERNAL_URL ?? 'http://collector:8000'
    const response = await fetch(`${base}/health`, {
      cache: 'no-store',
      signal: AbortSignal.timeout(3000),
    })
    collector = response.ok ? await response.json() : null
    if (!response.ok) collectorError = `수집기가 ${response.status}를 반환했습니다.`
  } catch (error) {
    // 수집기에 닿지 못해도 DB 요약은 보여준다.
    collectorError = error instanceof Error ? error.message : '수집기에 연결할 수 없습니다.'
  }

  return NextResponse.json({ ...summary, collector, collectorError })
}
```

`apps/web/app/api/admin/collect/route.ts` — 수집기 내부 API로 위임한다. 웹은 직접 수집하지 않는다.

```ts
import { NextResponse } from 'next/server'
import { parseDateField } from '@/lib/validate'

export async function POST(request: Request) {
  const body = (await request.json().catch(() => null)) as { tradeDate?: string } | null
  const parsed = parseDateField(body?.tradeDate, '거래일')
  if (!parsed.ok) return NextResponse.json({ error: parsed.error }, { status: 400 })

  const base = process.env.COLLECTOR_INTERNAL_URL ?? 'http://collector:8000'

  try {
    const response = await fetch(`${base}/jobs/collect`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ tradeDate: body?.tradeDate }),
      signal: AbortSignal.timeout(60_000),
    })
    const payload = await response.json().catch(() => ({}))
    return NextResponse.json(payload, { status: response.status })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : '수집기에 연결할 수 없습니다.' },
      { status: 502 },
    )
  }
}
```

- [ ] **Step 5: 수집 상태 화면**

`apps/web/app/(app)/admin/page.tsx`:

```tsx
import { Card, CardTitle } from '@/components/ui/card'
import { Stat } from '@/components/ui/stat'
import { Badge } from '@/components/ui/badge'
import { Empty } from '@/components/ui/empty'
import { Table, Td, Th } from '@/components/ui/table'
import { CollectButton } from './collect-button'
import { getCollectionSummary, getRecentRuns } from '@/lib/queries/collection'
import { DASH } from '@/lib/money'

// dynamic 설정은 (app)/layout.tsx가 하위 전체에 적용하므로 여기 다시 쓰지 않는다.

const STATUS_TONE: Record<string, 'neutral' | 'up' | 'down'> = {
  SUCCESS: 'neutral',
  PARTIAL: 'up',
  NO_DATA: 'neutral',
  FAILED: 'up',
}

export default async function AdminPage() {
  const [summary, runs] = await Promise.all([getCollectionSummary(), getRecentRuns(20)])

  let collectorOk = false
  let collectorError: string | null = null
  try {
    const base = process.env.COLLECTOR_INTERNAL_URL ?? 'http://collector:8000'
    const response = await fetch(`${base}/health`, {
      cache: 'no-store',
      signal: AbortSignal.timeout(3000),
    })
    collectorOk = response.ok
    if (!response.ok) collectorError = `수집기가 ${response.status}를 반환했습니다.`
  } catch (error) {
    collectorError = error instanceof Error ? error.message : '수집기에 연결할 수 없습니다.'
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold tracking-tight">수집 상태</h1>

      <Card>
        <div className="grid gap-6 sm:grid-cols-4">
          <Stat
            label="마지막 성공 수집"
            value={summary.lastSuccessAt ? summary.lastSuccessAt.slice(0, 16).replace('T', ' ') : DASH}
            sub={summary.lastSuccessDate ? `거래일 ${summary.lastSuccessDate}` : null}
          />
          <Stat label="누적 실패" value={String(summary.failureCount)} sub="건" />
          <Stat label="적재 행수" value={summary.marketCount.toLocaleString('ko-KR')} sub="rec_market" />
          <div>
            <p className="text-sm text-[var(--color-muted)]">수집기</p>
            <p className="mt-1">
              <Badge tone={collectorOk ? 'neutral' : 'up'}>{collectorOk ? '정상' : '연결 불가'}</Badge>
            </p>
            {collectorError ? (
              <p className="mt-1 text-xs text-[var(--color-muted)]">{collectorError}</p>
            ) : null}
          </div>
        </div>
      </Card>

      <Card>
        <CardTitle>수동 수집</CardTitle>
        <CollectButton />
        <p className="mt-2 text-xs text-[var(--color-muted)]">
          수집은 웹이 직접 하지 않고 수집기에 위임합니다. 수집기에 닿지 못하면 502가 반환됩니다.
        </p>
      </Card>

      <Card>
        <CardTitle>최근 실행</CardTitle>
        {runs.length === 0 ? (
          <div className="mt-4">
            <Empty title="수집 이력이 없습니다" />
          </div>
        ) : (
          <div className="mt-4">
            <Table>
              <thead>
                <tr>
                  <Th>거래일</Th>
                  <Th>종류</Th>
                  <Th>상태</Th>
                  <Th align="right">적재</Th>
                  <Th align="right">시작</Th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.id}>
                    <Td>{run.targetDate ?? DASH}</Td>
                    <Td>{run.jobType}</Td>
                    <Td>
                      <Badge tone={STATUS_TONE[run.status] ?? 'neutral'}>{run.status}</Badge>
                      {run.errorMessage ? (
                        <span className="ml-2 text-xs text-[var(--color-muted)]">{run.errorMessage}</span>
                      ) : null}
                    </Td>
                    <Td align="right">{run.rowsUpserted}</Td>
                    <Td align="right">{run.startedAt.slice(0, 16).replace('T', ' ')}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>
        )}
      </Card>
    </div>
  )
}
```

`apps/web/app/(app)/admin/collect-button.tsx`:

```tsx
'use client'

import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { Button } from '@/components/ui/button'

export function CollectButton() {
  const router = useRouter()
  const [tradeDate, setTradeDate] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  async function run() {
    setPending(true)
    setMessage(null)

    const response = await fetch('/api/admin/collect', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ tradeDate }),
    })
    const payload = (await response.json().catch(() => ({}))) as Record<string, unknown>

    setMessage(
      response.ok
        ? `${payload.status} · ${payload.rowsUpserted}행 적재`
        : String(payload.error ?? '수집에 실패했습니다.'),
    )
    setPending(false)
    if (response.ok) router.refresh()
  }

  return (
    <div className="mt-4 flex flex-wrap items-end gap-2">
      <label className="text-sm">
        <span className="text-[var(--color-muted)]">거래일</span>
        <input
          type="date"
          value={tradeDate}
          onChange={(event) => setTradeDate(event.target.value)}
          className="mt-1 block rounded-md border border-[var(--color-line)] bg-[var(--color-canvas)] px-2.5 py-1.5 text-sm outline-none focus:border-[var(--color-accent)]"
        />
      </label>
      <Button type="button" onClick={run} disabled={pending || tradeDate === ''}>
        {pending ? '수집 중…' : '수집 실행'}
      </Button>
      {message ? <span className="text-sm text-[var(--color-muted)]">{message}</span> : null}
    </div>
  )
}
```

로컬에서 웹을 호스트에서 실행하면 `http://collector:8000`에 닿을 수 없다. **이것은 오류가 아니다.** `연결 불가`가 표시되고 DB 요약은 정상 표시되면 통과다. Docker 안에서 웹을 함께 띄우는 것은 계획 C에서 다룬다.

- [ ] **Step 6: 확인**

```powershell
npm run dev
```

1. `/settings`에서 목표가격 `1차 매도 검토 / 75000` 등록 → 표에 나타나고 현재가 대비가 계산된다
2. `/admin`에서 마지막 성공 수집과 최근 실행 목록이 보인다
3. `/admin`의 수집기 상태가 `연결 불가`로 표시된다 (호스트 실행 시 정상)
4. `/dashboard`의 목표가격 칸에 등록한 목표가가 나타난다

- [ ] **Step 7: 전체 테스트와 빌드**

```powershell
cd C:\Dev\RECFlow
npm run test
npm run build
```

Expected: 테스트 전부 통과, 빌드 성공

- [ ] **Step 8: README 갱신**

`README.md`의 "현재 상태" 표에서 계획 B를 **완료**로 바꾸고, "시작하기"에 웹 실행 절차를 추가한다.

```markdown
### 5. 웹 실행

```powershell
npm run dev
```

`http://localhost:3000`에서 `.env`의 `APP_PASSWORD`로 로그인한다.

| 경로 | 내용 |
|---|---|
| `/dashboard` | 시세 요약, 가격 추이, 보유 평가액, 매각 판단 |
| `/market` | 기간별 지표, 이동평균, 거래량, 가격 위치 |
| `/inventory` | 발전소·발급·매각 등록과 발전소별 집계 |
| `/simulation` | 목표가별·분할 매각 시뮬레이션 |
| `/settings` | 목표가격 |
| `/admin` | 수집 상태와 수동 재수집 |

호스트에서 실행하면 `/admin`의 수집기 상태가 `연결 불가`로 나온다.
수집기는 Docker 내부 네트워크에만 있으므로 정상이다.
```

- [ ] **Step 9: 커밋**

```powershell
git add -A
git commit -m "feat(web): 목표가격과 수집 상태 화면 추가

수동 재수집은 웹이 직접 수행하지 않고 수집기 내부 API로 위임한다.
수집과 조회의 책임을 섞지 않는다.

수집기에 닿지 못해도 DB 요약은 그대로 보여준다. 호스트에서 웹만
실행하면 내부 네트워크에 접근할 수 없어 연결 불가가 뜨는데
이는 오류가 아니라 정상이다."
```

---

## 완료 기준

계획 B는 아래가 모두 참일 때 완료된다.

1. `npm run test`가 전부 통과한다 (순수 함수 테스트 90개 내외).
2. `npm run build`가 성공한다.
3. 로그인하지 않으면 모든 화면이 `/login`으로, 모든 API가 401로 막힌다.
4. `/dashboard`가 실제 313 거래일 데이터로 시세·차트·평가액·매각 판단을 표시한다.
5. `/market`의 기간 탭 6개가 동작하고, 짧은 기간에서는 MA26·MA52가 사라진다.
6. `/inventory`에서 보유량을 넘는 매각이 409로 거절된다.
7. `/simulation`의 분할매각 평균 매도가가 **가중평균**이다 (예시 조합에서 75,300원).
8. 데이터가 부족한 지표가 0이 아니라 `—`로 표시된다.
9. `prisma/schema.prisma`가 변경되지 않았다.

## 설계문서·계획서에서 변경한 사항

| 항목 | 원안 | 이 계획 | 이유 |
|---|---|---|---|
| UI 컴포넌트 | shadcn/ui | 직접 작성한 프리미티브 6개 | shadcn CLI가 대화형 프롬프트를 띄워 자동화 환경에서 멈춘다. API 형태를 맞춰 두어 나중에 교체할 수 있다 |
| 인증 게이트 | `middleware.ts` | `proxy.ts` (export `proxy`) | Next 16에서 이름이 바뀌었고 Node 런타임에서 돈다 |
| `GET /api/rec/chart` | 계획서 12장에 있음 | 만들지 않음 | `/api/rec/history`가 같은 데이터를 준다. 이동평균은 클라이언트가 아니라 서버 컴포넌트에서 계산하므로 별도 차트 전용 엔드포인트가 필요 없다 |
| 지표 타입 | 전부 Decimal | 통계는 `number`, 금액은 `Decimal` | 원 단위 가격은 배정밀도로 정확하고 차트가 `number`를 요구한다. 정밀도가 중요한 것은 합계 금액이다 |

## 계획 B에서 하지 않는 것

- SMP 연계, Telegram 알림 (Phase 4)
- 운영 compose, Caddy, 자동백업, 웹 컨테이너화 (계획 C)
- 컴포넌트 단위 테스트, E2E 테스트
- 사용자별 계정, 권한 구분
