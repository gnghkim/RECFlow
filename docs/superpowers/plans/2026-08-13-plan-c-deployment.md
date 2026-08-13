# 계획 C — 배포와 운영 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 계획 A의 수집기와 계획 B의 웹을 Ubuntu VPS에서 Docker Compose로 운영한다. Caddy가 HTTPS를 맡고, PostgreSQL은 자동 백업되며, 웹만 외부에 노출된다.

**Architecture:** 운영용 compose가 `caddy` / `web` / `collector` / `db` / `db-backup` 다섯 서비스를 띄운다. `caddy`와 `web`만 외부 공유 네트워크 `edge`에 붙고, `db`와 `collector`는 RECFlow 전용 내부망에만 존재한다. 향후 다른 사내 서비스는 `edge`에 합류해 Caddyfile에 사이트 블록만 추가하면 되며 RECFlow의 DB에는 닿을 수 없다.

**Tech Stack:** Docker Compose, Caddy 2.11, PostgreSQL 16, Node 24 (multi-stage build), Ubuntu LTS

**설계문서:** `docs/superpowers/specs/2026-08-12-rec-price-tracker-design.md` 8장 — 충돌 시 설계문서가 우선한다.
**선행 계획:** 계획 A(완료), 계획 B(완료)

---

## Global Constraints

- 작업 디렉토리는 `C:\Dev\RECFlow`. git 저장소이며 브랜치 `main`, 원격 `origin`.
- 개발 호스트는 **Windows 11 + PowerShell**. `&&`는 파서 오류를 내므로 `;`와 `if ($?) { }`를 쓴다.
- **이 계획의 대부분은 로컬에서 검증한다.** VPS에 실제 배포하는 것은 사람이 SSH로 수행하며, 이 계획은 그 절차를 문서로 남기는 것까지다. 워커가 VPS에 접속하려 시도하지 말 것.
- **이미지 버전 고정** (2026-08-13 확인값):

  | 이미지 | 태그 |
  |---|---|
  | `postgres` | `16-alpine` (기존 데이터 볼륨이 16이므로 **올리지 말 것**) |
  | `caddy` | `2.11.4-alpine` |
  | `node` (웹 빌드·실행) | `24-slim` |
  | `python` (수집기) | `3.12-slim` (계획 A에서 고정) |

- **기존 파일을 깨뜨리지 말 것.** `docker-compose.yml`(로컬 개발용)은 그대로 두고 운영용은 별도 파일에 쓴다. 로컬 개발 흐름이 계속 동작해야 한다.
- `prisma/schema.prisma`, `apps/collector/**`, `apps/web/**`의 애플리케이션 코드를 수정하지 않는다. 예외는 Task 1이 명시한 `next.config.ts` 확인뿐이다.
- 비밀값은 `.env`로만 관리하고 커밋하지 않는다.
- 각 Task는 마지막에 커밋으로 끝난다.
- **이번 범위에서 하지 않는 것**: 백업의 외부 복제(S3/R2) 구현, SMP, Telegram 알림, CI/CD 파이프라인, 모니터링 스택.

### 확정된 운영 전제

| 항목 | 값 |
|---|---|
| 도메인 | **보유**. `rec.<회사도메인>` 형태의 서브도메인을 VPS IP로 지정할 수 있다 |
| HTTPS | Caddy 자동 발급 (Let's Encrypt) |
| 백업 | **VPS 내부 보관까지만.** 외부 복제는 문서에 절차만 남긴다 |
| DB 포트 | 운영에서 호스트에 **노출하지 않는다** |
| 수집기 포트 | 운영에서 호스트에 **노출하지 않는다** |

### 계획 A·B에서 이어지는 사실

- `apps/web/next.config.ts`에 `output: 'standalone'`과 `outputFileTracingRoot`가 이미 설정되어 있다.
- `next.config.ts`가 `process.loadEnvFile`로 저장소 루트 `.env`를 읽지만, **존재할 때만** 읽는다. 운영 컨테이너에는 `.env` 파일이 없고 compose가 환경변수를 직접 주입하므로 문제가 없다.
- npm workspaces 루트는 저장소 루트이고 워크스페이스는 `apps/web` 하나다. Prisma 도구도 루트에 있다.
- 수집기 이미지(`apps/collector/Dockerfile`)는 이미 존재하며 앱 구동과 테스트에 공용으로 쓴다.
- `app/(app)/layout.tsx`의 `force-dynamic` 덕분에 웹은 빌드 시점 데이터를 굽지 않는다. 빌드 시 DB 연결이 필요 없다.

---

## File Structure

| 파일 | 책임 |
|---|---|
| `apps/web/Dockerfile` | 웹 멀티스테이지 빌드 (deps → build → runner) |
| `apps/web/.dockerignore` | 빌드 컨텍스트 축소 |
| `docker-compose.prod.yml` | 운영 5개 서비스 |
| `infra/caddy/Caddyfile` | HTTPS와 리버스프록시 |
| `infra/backup/Dockerfile` | pg_dump 실행 이미지 |
| `infra/backup/backup.sh` | 덤프 생성과 보관정책 적용 |
| `infra/backup/entrypoint.sh` | 매일 02:00 실행 루프 |
| `infra/scripts/restore.sh` | 복구 절차 스크립트 |
| `.env.prod.example` | 운영 환경변수 목록 |
| `docs/deployment.md` | VPS 초기 설정부터 배포·운영까지 |

---

### Task 1: 웹 컨테이너 이미지

**Files:**
- Create: `apps/web/Dockerfile`
- Create: `.dockerignore` (저장소 루트. 빌드 컨텍스트가 루트이므로 여기여야 적용된다)
- Modify: `.gitignore` (필요 시)

**Interfaces:**
- Consumes: 루트 `package.json`, `package-lock.json`, `prisma/schema.prisma`, `apps/web/**`
- Produces: `recflow-web` 이미지. 3000 포트에서 Next standalone 서버 구동. 환경변수 `DATABASE_URL`, `APP_PASSWORD`, `AUTH_SECRET`, `COLLECTOR_INTERNAL_URL`을 런타임에 받는다.

- [ ] **Step 1: `.dockerignore` 작성**

**저장소 루트의 `.dockerignore`**에 쓴다. Docker는 빌드 컨텍스트 최상단의 `.dockerignore`만
읽으므로 `apps/web/.dockerignore`를 만들면 무시된다. 동작하지 않는 파일을 두면 나중에 누가 보고
적용된다고 착각한다.

수집기 빌드는 영향받지 않는다. 컨텍스트가 `./apps/collector`라 그쪽 `.dockerignore`를 읽는다.
루트 컨텍스트를 쓰는 빌드는 웹 하나뿐이다.

```text
**/node_modules
**/.next
**/.venv
**/__pycache__
**/.pytest_cache
apps/collector/fixtures
apps/collector/api-samples
.git
.env
.env.*
!.env.example
docs
infra/backup/dumps
```

- [ ] **Step 2: standalone 출력 구조를 먼저 확인한다**

Dockerfile의 `CMD` 경로는 `outputFileTracingRoot` 설정에 따라 달라진다. **추측하지 말고 실제 구조를 확인한다.**

```powershell
cd C:\Dev\RECFlow
npm run build
Get-ChildItem -Recurse apps\web\.next\standalone -Filter server.js | ForEach-Object { $_.FullName.Replace('C:\Dev\RECFlow\','') }
```

Expected: `apps/web/.next/standalone/apps/web/server.js` 형태의 경로가 출력된다. 만약 `apps/web/.next/standalone/server.js`처럼 다르게 나오면 아래 Dockerfile의 `CMD`와 `COPY` 경로를 실제 구조에 맞게 조정하고, 무엇이 달랐는지 커밋 메시지에 적는다.

- [ ] **Step 3: `apps/web/Dockerfile` 작성**

빌드 컨텍스트는 **저장소 루트**다. npm workspaces와 Prisma가 루트에 있기 때문이다.

```dockerfile
# syntax=docker/dockerfile:1

# --- 1단계: 의존성 -----------------------------------------------------------
FROM node:24-slim AS deps
WORKDIR /repo

# 루트가 워크스페이스 루트이고 Prisma 도구도 루트에 있다.
COPY package.json package-lock.json ./
COPY apps/web/package.json apps/web/package.json
COPY prisma prisma

# postinstall에서 prisma generate가 돌 수 있도록 스키마를 먼저 복사했다.
RUN npm ci

# --- 2단계: 빌드 -------------------------------------------------------------
FROM node:24-slim AS builder
WORKDIR /repo

COPY --from=deps /repo/node_modules node_modules
COPY package.json package-lock.json ./
COPY prisma prisma
COPY apps/web apps/web

# Prisma 클라이언트를 생성한다. 빌드 시 DB 연결은 필요 없지만
# datasource url 파싱을 위해 형식만 갖춘 값이 있어야 한다.
ENV DATABASE_URL="postgresql://build:build@localhost:5432/build"
RUN npx prisma generate --schema prisma/schema.prisma

ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build --workspace apps/web

# --- 3단계: 실행 -------------------------------------------------------------
FROM node:24-slim AS runner
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0 \
    TZ=Asia/Seoul

# root로 돌리지 않는다.
RUN groupadd --system --gid 1001 nodejs \
 && useradd --system --uid 1001 --gid nodejs nextjs

# standalone 출력에는 필요한 node_modules가 이미 추려져 들어있다.
COPY --from=builder --chown=nextjs:nodejs /repo/apps/web/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /repo/apps/web/.next/static ./apps/web/.next/static
COPY --from=builder --chown=nextjs:nodejs /repo/apps/web/public ./apps/web/public

USER nextjs
EXPOSE 3000

CMD ["node", "apps/web/server.js"]
```

`apps/web/public`이 없으면 해당 `COPY` 줄을 지운다. 없는 경로를 복사하면 빌드가 실패한다.

- [ ] **Step 4: 이미지 빌드 확인**

```powershell
cd C:\Dev\RECFlow
docker build -f apps/web/Dockerfile -t recflow-web:test .
```

Expected: 빌드 성공. 실패하면 Step 2에서 확인한 실제 경로와 `COPY` 대상이 맞는지 먼저 본다.

- [ ] **Step 5: 컨테이너 단독 기동 확인**

DB 없이도 서버는 떠야 한다. 화면은 DB 오류를 낼 수 있지만 프로세스가 죽으면 안 된다.

```powershell
docker run --rm -d --name recflow-web-test -p 3100:3000 `
  -e DATABASE_URL="postgresql://x:x@127.0.0.1:5432/x" `
  -e APP_PASSWORD="test-password" `
  -e AUTH_SECRET="test-secret-that-is-at-least-32-characters" `
  recflow-web:test
Start-Sleep -Seconds 8
try { $r = Invoke-WebRequest -Uri http://localhost:3100/login -UseBasicParsing -TimeoutSec 5; "login status=$($r.StatusCode)" } catch { "실패: $($_.Exception.Message)" }
docker logs recflow-web-test --tail 20
docker stop recflow-web-test
```

Expected: `/login`이 200을 반환한다. 로그인 화면은 DB를 읽지 않으므로 DB가 없어도 떠야 한다.

- [ ] **Step 6: 이미지 크기 확인**

```powershell
docker images recflow-web:test --format "{{.Size}}"
```

Expected: 대략 200~400MB. 1GB를 넘으면 `.dockerignore`가 제대로 동작하지 않은 것이므로 확인한다.

- [ ] **Step 7: 커밋**

```powershell
cd C:\Dev\RECFlow
git add apps/web/Dockerfile .dockerignore
git commit -m "feat(deploy): 웹 컨테이너 이미지 추가

빌드 컨텍스트는 저장소 루트다. npm workspaces와 Prisma 스키마가
루트에 있어 apps/web 만으로는 빌드할 수 없다.

standalone 출력을 쓰므로 실행 이미지에 추려진 node_modules만 들어간다.
root가 아닌 nextjs 사용자로 구동한다. 빌드 시 DB 연결은 필요 없다.
force-dynamic 덕분에 빌드 시점 데이터를 굽지 않기 때문이다."
```

---

### Task 2: 운영 compose와 Caddy

**Files:**
- Create: `docker-compose.prod.yml`
- Create: `infra/caddy/Caddyfile`
- Create: `.env.prod.example`

**Interfaces:**
- Consumes: Task 1의 웹 이미지, 계획 A의 `apps/collector/Dockerfile`
- Produces: `docker compose -f docker-compose.prod.yml up -d`로 기동되는 5개 서비스. 외부 공유 네트워크 `edge`.

- [ ] **Step 1: `.env.prod.example` 작성**

운영 VPS의 `.env`가 될 파일이다. 로컬 개발용 `.env.example`과 별도로 둔다.

```text
# ── 운영 환경변수. VPS의 /opt/recflow/.env 로 복사해 채운다. ──
# 이 파일은 예시일 뿐이며 실제 값이 든 .env 는 절대 커밋하지 않는다.

# --- 도메인 ---
# Caddy가 이 이름으로 인증서를 발급한다. DNS A 레코드가 VPS IP를 가리켜야 한다.
RECFLOW_DOMAIN=rec.example.co.kr
# Let's Encrypt 만료 알림을 받을 주소
ACME_EMAIL=admin@example.co.kr

# --- Database ---
POSTGRES_DB=recflow
POSTGRES_USER=recflow
# openssl rand -base64 32 등으로 생성
POSTGRES_PASSWORD=
# 호스트는 db 이며 컨테이너 네트워크 이름이다. localhost가 아니다.
DATABASE_URL=postgresql://recflow:CHANGE_ME@db:5432/recflow

# --- KPX Open API ---
KPX_API_KEY=
KPX_BASE_URL=https://apis.data.go.kr/B552115/RecMarketInfo2
KPX_DAILY_BUDGET=80

# --- Web ---
# 사내 로그인 비밀번호
APP_PASSWORD=
# 세션 서명 키. 32자 이상. openssl rand -base64 32
AUTH_SECRET=
COLLECTOR_INTERNAL_URL=http://collector:8000

# --- 공통 ---
TZ=Asia/Seoul

# --- 백업 ---
# 일별 보관 일수 / 주별 보관 주수 / 월별 보관 개월수
BACKUP_KEEP_DAILY=7
BACKUP_KEEP_WEEKLY=4
BACKUP_KEEP_MONTHLY=12
```

- [ ] **Step 2: `infra/caddy/Caddyfile` 작성**

```text
{
	email {$ACME_EMAIL}
}

{$RECFLOW_DOMAIN} {
	encode zstd gzip

	# 웹만 외부에 노출한다. 수집기와 DB로 가는 경로는 존재하지 않는다.
	reverse_proxy web:3000

	header {
		Strict-Transport-Security "max-age=31536000; includeSubDomains"
		X-Content-Type-Options "nosniff"
		X-Frame-Options "DENY"
		Referrer-Policy "strict-origin-when-cross-origin"
		-Server
	}

	log {
		output file /var/log/caddy/recflow.log {
			roll_size 10MiB
			roll_keep 5
		}
	}
}
```

향후 다른 사내 서비스를 추가할 때는 이 파일에 사이트 블록을 하나 더 쓰고 해당 서비스를 `edge` 네트워크에 붙이면 된다. RECFlow의 DB에는 닿을 수 없다.

- [ ] **Step 3: `docker-compose.prod.yml` 작성**

```yaml
# 운영 전용. 로컬 개발은 docker-compose.yml 을 쓴다.
#
# 네트워크가 둘로 갈린다.
#   edge     : caddy 와 web 만. 다른 사내 서비스가 나중에 합류한다.
#   internal : db 와 collector. 외부에서 닿을 수 없다.
# 이렇게 두면 나중에 edge 에 붙는 서비스가 RECFlow 의 DB에 접근하지 못한다.

services:
  caddy:
    image: caddy:2.11.4-alpine
    container_name: recflow-caddy
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
      - "443:443/udp"
    environment:
      RECFLOW_DOMAIN: ${RECFLOW_DOMAIN}
      ACME_EMAIL: ${ACME_EMAIL}
    volumes:
      - ./infra/caddy/Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
      - caddy_logs:/var/log/caddy
    networks:
      - edge
    depends_on:
      - web

  web:
    build:
      context: .
      dockerfile: apps/web/Dockerfile
    image: recflow-web:latest
    container_name: recflow-web
    restart: unless-stopped
    environment:
      DATABASE_URL: ${DATABASE_URL}
      APP_PASSWORD: ${APP_PASSWORD}
      AUTH_SECRET: ${AUTH_SECRET}
      COLLECTOR_INTERNAL_URL: ${COLLECTOR_INTERNAL_URL}
      TZ: ${TZ}
    # 호스트 포트를 열지 않는다. Caddy만 접근한다.
    networks:
      - edge
      - internal
    depends_on:
      db:
        condition: service_healthy

  collector:
    build:
      context: ./apps/collector
    image: recflow-collector:latest
    container_name: recflow-collector
    restart: unless-stopped
    environment:
      DATABASE_URL: ${DATABASE_URL}
      KPX_API_KEY: ${KPX_API_KEY}
      KPX_BASE_URL: ${KPX_BASE_URL}
      KPX_DAILY_BUDGET: ${KPX_DAILY_BUDGET}
      FIXTURE_DIR: /app/fixtures
      TZ: ${TZ}
    volumes:
      - collector_fixtures:/app/fixtures
      - collector_samples:/app/api-samples
    # 호스트 포트를 열지 않는다. 웹이 내부망으로만 호출한다.
    networks:
      - internal
    depends_on:
      db:
        condition: service_healthy

  db:
    image: postgres:16-alpine
    container_name: recflow-db
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      TZ: ${TZ}
    # 운영에서는 호스트 포트를 절대 열지 않는다.
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - internal
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 10

  db-backup:
    build:
      context: ./infra/backup
    image: recflow-backup:latest
    container_name: recflow-backup
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      PGPASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_HOST: db
      BACKUP_KEEP_DAILY: ${BACKUP_KEEP_DAILY}
      BACKUP_KEEP_WEEKLY: ${BACKUP_KEEP_WEEKLY}
      BACKUP_KEEP_MONTHLY: ${BACKUP_KEEP_MONTHLY}
      TZ: ${TZ}
    volumes:
      - ./infra/backup/dumps:/dumps
    networks:
      - internal
    depends_on:
      db:
        condition: service_healthy

volumes:
  postgres_data:
  caddy_data:
  caddy_config:
  caddy_logs:
  collector_fixtures:
  collector_samples:

networks:
  edge:
    name: edge
    external: true
  internal:
    name: recflow-internal
```

`edge`는 `external: true`이므로 **compose 밖에서 먼저 만들어야 한다.** 배포 문서에 절차를 넣는다. 이렇게 해야 다른 사내 서비스의 compose가 같은 네트워크에 합류할 수 있다.

- [ ] **Step 4: compose 문법 검증**

```powershell
cd C:\Dev\RECFlow
Copy-Item .env.prod.example .env.prod
docker compose -f docker-compose.prod.yml --env-file .env.prod config | Select-Object -First 30
```

Expected: 해석된 설정이 출력된다. `edge` 네트워크가 없다는 오류가 나오면 정상이며 다음 단계에서 만든다.

- [ ] **Step 5: 포트 노출 검증**

```powershell
docker compose -f docker-compose.prod.yml --env-file .env.prod config | Select-String -Pattern 'published|ports' -Context 1,2
```

Expected: `published`가 나타나는 서비스는 **caddy 하나뿐**이고 80·443만 열려 있다. `db`, `collector`, `web`에 published가 있으면 설계 위반이므로 제거한다.

- [ ] **Step 6: 임시 파일 정리와 gitignore**

`.gitignore`에 아래를 추가한다. 기존 `.env.*` 규칙이 `.env.prod.example`까지 무시하므로
**예외를 명시해야 한다.** 빠뜨리면 배포 문서만 있고 예시 파일이 없는 상태가 된다.

```text
# 운영 환경변수 (예시 파일만 커밋한다)
.env.prod
!.env.prod.example
# 백업 산출물
infra/backup/dumps/
```

추가 후 실제로 추적 대상이 되는지 확인한다.

```powershell
git check-ignore -v .env.prod.example
```

Expected: 아무것도 출력되지 않는다(무시되지 않음). 규칙이 출력되면 예외가 적용되지 않은 것이다.

```powershell
Remove-Item C:\Dev\RECFlow\.env.prod -ErrorAction SilentlyContinue
```

- [ ] **Step 7: 커밋**

```powershell
git add docker-compose.prod.yml infra/caddy/Caddyfile .env.prod.example .gitignore
git commit -m "feat(deploy): 운영 compose와 Caddy 설정 추가

네트워크를 edge 와 internal 로 나눴다. caddy 와 web 만 edge 에 붙고
db 와 collector 는 내부망에만 있다. 나중에 다른 사내 서비스가 edge 에
합류해도 RECFlow 의 DB에는 닿을 수 없다.

호스트 포트는 caddy 의 80 443 만 연다. db 와 collector 는 물론
web 도 열지 않는다. 외부 트래픽은 전부 Caddy를 지난다."
```

---

### Task 3: 자동 백업

**Files:**
- Create: `infra/backup/Dockerfile`
- Create: `infra/backup/backup.sh`
- Create: `infra/backup/entrypoint.sh`
- Create: `infra/scripts/restore.sh`

**Interfaces:**
- Consumes: `db` 서비스, 환경변수 `POSTGRES_*`, `BACKUP_KEEP_*`
- Produces: `/dumps/daily|weekly|monthly/recflow-YYYYMMDD-HHMM.sql.gz`. 매일 02:00 실행.

- [ ] **Step 1: `infra/backup/backup.sh` 작성**

```bash
#!/bin/sh
# PostgreSQL 논리 백업. 보관정책은 일별 7 / 주별 4 / 월별 12를 기본으로 한다.
#
# REC 가격 이력은 화·목에만 생성되므로 잃으면 다시 만들 수 없다.
# 실패를 조용히 넘기지 않고 즉시 비정상 종료한다.
set -eu

DUMP_ROOT=/dumps
TIMESTAMP=$(date +%Y%m%d-%H%M)
DAY_OF_WEEK=$(date +%u)   # 1=월 … 7=일
DAY_OF_MONTH=$(date +%d)

mkdir -p "$DUMP_ROOT/daily" "$DUMP_ROOT/weekly" "$DUMP_ROOT/monthly"

TARGET="$DUMP_ROOT/daily/recflow-$TIMESTAMP.sql.gz"
TMP="$TARGET.partial"

echo "[$(date '+%F %T')] 백업 시작: $TARGET"

# 먼저 임시 이름으로 쓰고 성공했을 때만 최종 이름으로 옮긴다.
# 중간에 실패한 파일이 정상 백업처럼 보이면 안 된다.
pg_dump \
  --host="$POSTGRES_HOST" \
  --username="$POSTGRES_USER" \
  --dbname="$POSTGRES_DB" \
  --format=plain \
  --no-owner \
  --no-privileges \
  | gzip -9 > "$TMP"

# 파이프라인이라 pg_dump 실패가 gzip 성공에 가려질 수 있다. 크기로 확인한다.
if [ ! -s "$TMP" ]; then
  echo "[$(date '+%F %T')] 실패: 덤프가 비어 있다" >&2
  rm -f "$TMP"
  exit 1
fi

mv "$TMP" "$TARGET"
echo "[$(date '+%F %T')] 완료: $(du -h "$TARGET" | cut -f1)"

# 일요일 백업은 주별로도 남긴다.
if [ "$DAY_OF_WEEK" = "7" ]; then
  cp "$TARGET" "$DUMP_ROOT/weekly/recflow-$TIMESTAMP.sql.gz"
  echo "주별 사본 생성"
fi

# 매월 1일 백업은 월별로도 남긴다.
if [ "$DAY_OF_MONTH" = "01" ]; then
  cp "$TARGET" "$DUMP_ROOT/monthly/recflow-$TIMESTAMP.sql.gz"
  echo "월별 사본 생성"
fi

prune() {
  directory="$1"
  keep="$2"
  count=$(ls -1 "$directory" 2>/dev/null | wc -l)
  if [ "$count" -gt "$keep" ]; then
    ls -1t "$directory" | tail -n +$((keep + 1)) | while read -r old; do
      rm -f "$directory/$old"
      echo "정리: $directory/$old"
    done
  fi
}

prune "$DUMP_ROOT/daily" "${BACKUP_KEEP_DAILY:-7}"
prune "$DUMP_ROOT/weekly" "${BACKUP_KEEP_WEEKLY:-4}"
prune "$DUMP_ROOT/monthly" "${BACKUP_KEEP_MONTHLY:-12}"

echo "[$(date '+%F %T')] 백업 종료"
```

- [ ] **Step 2: `infra/backup/entrypoint.sh` 작성**

```bash
#!/bin/sh
# 매일 02:00(Asia/Seoul)에 백업을 실행한다.
#
# cron 대신 잠자기 루프를 쓴다. 컨테이너 안의 cron은 환경변수를 상속받지
# 못해 별도 설정이 필요하고, 로그가 docker logs 에 보이지 않는다.
set -eu

echo "백업 스케줄러 시작. 매일 02:00 ($(date +%Z)) 실행"

while true; do
  now=$(date +%s)
  # 오늘 02:00. 이미 지났으면 내일 02:00.
  target=$(date -d "$(date +%F) 02:00" +%s 2>/dev/null || echo 0)
  if [ "$target" -le "$now" ]; then
    target=$(date -d "$(date +%F) 02:00 + 1 day" +%s)
  fi

  sleep_seconds=$((target - now))
  echo "다음 백업까지 ${sleep_seconds}초 대기"
  sleep "$sleep_seconds"

  # 백업이 실패해도 스케줄러는 계속 돈다. 하루 실패로 이후 백업이
  # 전부 멈추면 더 나쁘다. 실패는 로그에 남는다.
  /usr/local/bin/backup.sh || echo "백업 실패. 다음 주기에 재시도한다" >&2
done
```

- [ ] **Step 3: `infra/backup/Dockerfile` 작성**

```dockerfile
# db 와 같은 major 를 써야 pg_dump 가 호환된다.
FROM postgres:16-alpine

ENV TZ=Asia/Seoul

# alpine 의 date 는 -d 옵션을 제한적으로 지원하므로 coreutils 를 넣는다.
RUN apk add --no-cache coreutils tzdata

COPY backup.sh /usr/local/bin/backup.sh
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/backup.sh /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
```

- [ ] **Step 4: `infra/scripts/restore.sh` 작성**

복구는 드물게 하는 일이라 그때 방법을 찾게 된다. 스크립트로 남긴다.

```bash
#!/bin/sh
# 백업 파일에서 복구한다.
#
#   ./infra/scripts/restore.sh infra/backup/dumps/daily/recflow-20260813-0200.sql.gz
#
# 주의: 대상 데이터베이스의 기존 데이터를 덮어쓴다.
set -eu

DUMP_FILE="${1:-}"
if [ -z "$DUMP_FILE" ] || [ ! -f "$DUMP_FILE" ]; then
  echo "사용법: $0 <덤프파일.sql.gz>" >&2
  exit 1
fi

echo "복구 대상: $DUMP_FILE"
echo "이 작업은 recflow 데이터베이스의 현재 내용을 덮어쓴다."
printf "계속하려면 yes 를 입력하라: "
read -r answer
[ "$answer" = "yes" ] || { echo "취소했다"; exit 1; }

echo "웹과 수집기를 멈춘다. 복구 중 쓰기가 들어오면 안 된다."
docker compose -f docker-compose.prod.yml stop web collector

echo "복구 실행"
gunzip -c "$DUMP_FILE" | docker compose -f docker-compose.prod.yml exec -T db \
  psql -U "${POSTGRES_USER:-recflow}" -d "${POSTGRES_DB:-recflow}"

echo "서비스를 다시 시작한다"
docker compose -f docker-compose.prod.yml start web collector

echo "복구 완료. 관리자 화면에서 적재 행수를 확인하라."
```

- [ ] **Step 5: 백업 이미지 빌드와 실제 실행 확인**

로컬 개발 DB를 대상으로 백업 스크립트가 실제로 도는지 확인한다.

먼저 로컬 개발 DB가 붙어 있는 네트워크 이름을 **확인한다.** 추측하지 않는다.

```powershell
cd C:\Dev\RECFlow
docker compose up -d db
$devNetwork = (docker inspect recflow-db --format '{{range $k, $v := .NetworkSettings.Networks}}{{$k}}{{end}}')
"개발 DB 네트워크 = $devNetwork"
```

그 이름으로 백업을 실행한다.

```powershell
docker build -t recflow-backup:test infra/backup
New-Item -ItemType Directory -Force infra\backup\dumps | Out-Null
$pgpw = ((Get-Content .env | Where-Object { $_ -like 'POSTGRES_PASSWORD=*' }) -split '=',2)[1].Trim()
docker run --rm --network $devNetwork `
  -e POSTGRES_HOST=db -e POSTGRES_USER=recflow -e POSTGRES_DB=recflow -e PGPASSWORD=$pgpw `
  -v "${PWD}\infra\backup\dumps:/dumps" `
  --entrypoint /usr/local/bin/backup.sh recflow-backup:test
```

Expected: `백업 완료`와 파일 크기가 출력된다. `could not translate host name` 오류가 나면 네트워크 이름이 틀린 것이다.

- [ ] **Step 6: 백업 내용 검증**

파일이 생겼다는 것만으로는 부족하다. **실제로 복구 가능한 내용인지** 확인한다.

```powershell
$dump = Get-ChildItem infra\backup\dumps\daily\*.sql.gz | Select-Object -First 1
"파일: $($dump.Name)  크기: $([math]::Round($dump.Length/1KB,1))KB"
docker run --rm -v "${PWD}\infra\backup\dumps:/dumps" recflow-backup:test sh -c "gunzip -c /dumps/daily/$($dump.Name) | grep -c 'INSERT INTO\|COPY '"
docker run --rm -v "${PWD}\infra\backup\dumps:/dumps" recflow-backup:test sh -c "gunzip -c /dumps/daily/$($dump.Name) | grep -o 'CREATE TABLE public\.[a-z_]*'"
```

Expected: `rec_market`을 포함한 테이블 7개의 `CREATE TABLE`이 보이고, 데이터 구문이 0보다 크다. 스키마만 있고 데이터가 없으면 `pg_dump` 옵션이 잘못된 것이다.

- [ ] **Step 7: 보관정책 검증**

```powershell
# 오래된 파일 10개를 만들어 정리가 도는지 본다
1..10 | ForEach-Object { $d = (Get-Date).AddDays(-$_).ToString('yyyyMMdd'); New-Item -ItemType File -Force "infra\backup\dumps\daily\recflow-$d-0200.sql.gz" | Out-Null }
"정리 전: $((Get-ChildItem infra\backup\dumps\daily).Count)개"
$pgpw = ((Get-Content .env | Where-Object { $_ -like 'POSTGRES_PASSWORD=*' }) -split '=',2)[1].Trim()
$devNetwork = (docker inspect recflow-db --format '{{range $k, $v := .NetworkSettings.Networks}}{{$k}}{{end}}')
docker run --rm --network $devNetwork -e POSTGRES_HOST=db -e POSTGRES_USER=recflow -e POSTGRES_DB=recflow -e PGPASSWORD=$pgpw -e BACKUP_KEEP_DAILY=7 -v "${PWD}\infra\backup\dumps:/dumps" --entrypoint /usr/local/bin/backup.sh recflow-backup:test | Select-String -Pattern '정리'
"정리 후: $((Get-ChildItem infra\backup\dumps\daily).Count)개 (7개여야 정상)"
```

Expected: 정리 후 7개가 남는다.

- [ ] **Step 8: 검증 산출물 정리**

```powershell
Remove-Item -Recurse -Force infra\backup\dumps -ErrorAction SilentlyContinue
```

- [ ] **Step 9: 커밋**

```powershell
git add infra/backup infra/scripts
git commit -m "feat(deploy): PostgreSQL 자동 백업 추가

매일 02:00 pg_dump 후 일별 7 주별 4 월별 12로 보관한다.

임시 이름으로 먼저 쓰고 성공했을 때만 최종 이름으로 옮긴다. 중간에
실패한 파일이 정상 백업처럼 보이면 복구 시점에야 알게 된다.
파이프라인이라 pg_dump 실패가 gzip 성공에 가려질 수 있어 크기도 확인한다.

cron 대신 잠자기 루프를 쓴다. 컨테이너 cron은 환경변수를 상속받지 못하고
로그가 docker logs 에 보이지 않는다. 백업 한 번 실패로 스케줄러가
멈추지 않게 실패를 흡수하고 로그에 남긴다."
```

---

### Task 4: 전체 스택 로컬 검증

**Files:**
- 없음 (검증만 수행)

**Interfaces:**
- Consumes: Task 1~3의 산출물 전부
- Produces: 운영 구성이 실제로 뜬다는 증거

VPS에 올리기 전에 운영 compose가 실제로 동작하는지 로컬에서 확인한다. 도메인과 HTTPS만 다르고 나머지는 같다.

> **반드시 `-p recflow-prod`를 붙여 실행한다.**
> Compose의 프로젝트 이름은 기본적으로 디렉토리 이름(`recflow`)이라, 같은 폴더의
> `docker-compose.yml`과 `docker-compose.prod.yml`이 **같은 볼륨 `recflow_postgres_data`를
> 공유한다.** 이 상태로 검증 끝에 `down -v`를 실행하면 **로컬 개발 DB의 939행이 삭제된다.**
> 프로젝트 이름을 나누면 볼륨이 `recflow-prod_postgres_data`로 분리되어 개발 데이터가 안전하다.
>
> 아래 모든 명령에 `-p recflow-prod`가 들어 있다. 하나라도 빠뜨리지 말 것.

- [ ] **Step 1: 로컬 검증용 Caddyfile 준비**

Let's Encrypt는 로컬에서 검증할 수 없다. 임시로 내부 HTTP만 확인한다.

```powershell
cd C:\Dev\RECFlow
Copy-Item .env.prod.example .env.prod
```

`.env.prod`를 열어 아래를 채운다.

```text
RECFLOW_DOMAIN=localhost
ACME_EMAIL=test@example.com
POSTGRES_PASSWORD=local-verify-password
DATABASE_URL=postgresql://recflow:local-verify-password@db:5432/recflow
APP_PASSWORD=local-verify-password
AUTH_SECRET=local-verification-secret-at-least-32-chars
```

Caddy는 `localhost`에 대해 내부 인증서를 자동으로 쓰므로 Let's Encrypt를 호출하지 않는다.

- [ ] **Step 2: 공유 네트워크 생성**

```powershell
docker network create edge 2>&1 | Out-Null
docker network ls | Select-String -Pattern 'edge'
```

- [ ] **Step 3: 기존 로컬 스택 중지**

`container_name`은 프로젝트와 무관하게 호스트 전역에서 유일해야 한다. `recflow-db`가 양쪽 compose에 있으므로 개발 스택을 먼저 내려야 한다. **`-v`를 붙이지 않는다.** 개발 볼륨을 지우면 939행이 사라진다.

```powershell
docker compose down
```

- [ ] **Step 4: 운영 스택 기동**

```powershell
docker compose -p recflow-prod -f docker-compose.prod.yml --env-file .env.prod up -d --build
Start-Sleep -Seconds 20
docker compose -p recflow-prod -f docker-compose.prod.yml --env-file .env.prod ps
```

Expected: 5개 서비스가 전부 `Up`이다. `db`는 `healthy`여야 한다.

- [ ] **Step 5: 스키마 적용**

새 볼륨이면 테이블이 없다. 마이그레이션을 적용한다.

```powershell
docker compose -p recflow-prod -f docker-compose.prod.yml --env-file .env.prod exec -T db psql -U recflow -d recflow -c "\dt"
```

테이블이 없으면 호스트에서 적용한다. 운영 DB는 포트가 닫혀 있으므로 컨테이너 안에서 실행해야 한다. 배포 문서에 절차를 넣되, 여기서는 아래로 확인한다.

```powershell
docker run --rm --network recflow-internal `
  -v "${PWD}/prisma:/prisma" `
  -e DATABASE_URL="postgresql://recflow:local-verify-password@db:5432/recflow" `
  node:24-slim sh -c "npm i -g prisma@6.19.3 && prisma migrate deploy --schema /prisma/schema.prisma"
docker compose -p recflow-prod -f docker-compose.prod.yml --env-file .env.prod exec -T db psql -U recflow -d recflow -c "\dt"
```

Expected: 테이블 8개가 보인다.

- [ ] **Step 6: 포트 노출 실제 확인**

```powershell
docker compose -p recflow-prod -f docker-compose.prod.yml --env-file .env.prod ps --format "table {{.Service}}\t{{.Ports}}"
```

Expected: `caddy`만 `0.0.0.0:80`, `0.0.0.0:443` 매핑을 갖는다. 나머지 넷은 호스트 매핑이 없다.

```powershell
foreach ($port in 5432, 8000, 3000) {
  try { $c = New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1', $port); "!!! $port 열림"; $c.Close() }
  catch { "OK: $port 닫힘" }
}
```

Expected: 세 포트 모두 닫혀 있다. **5432가 열려 있으면 설계 위반**이다.

- [ ] **Step 7: Caddy 경유 접근 확인**

```powershell
try { $r = Invoke-WebRequest -Uri https://localhost/login -UseBasicParsing -SkipCertificateCheck -TimeoutSec 10; "HTTPS status=$($r.StatusCode)" } catch { "실패: $($_.Exception.Message)" }
try { $r = Invoke-WebRequest -Uri http://localhost/login -UseBasicParsing -MaximumRedirection 0 -TimeoutSec 10; "HTTP status=$($r.StatusCode)" } catch { "HTTP -> $([int]$_.Exception.Response.StatusCode) (HTTPS 리다이렉트면 정상)" }
```

Expected: HTTPS가 200을, HTTP는 308 리다이렉트를 낸다.

- [ ] **Step 8: 수집기와 웹 연결 확인**

```powershell
docker compose -p recflow-prod -f docker-compose.prod.yml --env-file .env.prod exec -T web node -e "fetch('http://collector:8000/health').then(r=>r.json()).then(d=>console.log(JSON.stringify(d))).catch(e=>console.log('실패: '+e.message))"
```

Expected: `{"status":"ok",...}` — 웹이 내부망으로 수집기에 닿는다. 로컬 개발에서는 닿지 않던 경로가 운영 구성에서는 동작해야 한다.

- [ ] **Step 9: 백업 컨테이너 확인**

```powershell
docker compose -p recflow-prod -f docker-compose.prod.yml --env-file .env.prod logs db-backup --tail 10
docker compose -p recflow-prod -f docker-compose.prod.yml --env-file .env.prod exec -T db-backup /usr/local/bin/backup.sh
Get-ChildItem infra\backup\dumps\daily
```

Expected: 스케줄러 로그에 다음 실행까지 남은 시간이 보이고, 수동 실행이 덤프를 만든다.

- [ ] **Step 10: 정리**

```powershell
docker compose -p recflow-prod -f docker-compose.prod.yml --env-file .env.prod down -v
docker network rm edge 2>&1 | Out-Null
Remove-Item C:\Dev\RECFlow\.env.prod -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force C:\Dev\RECFlow\infra\backup\dumps -ErrorAction SilentlyContinue
docker compose up -d db
```

`-p recflow-prod`를 붙였으므로 `down -v`는 `recflow-prod_*` 볼륨만 지운다. 개발 볼륨
`recflow_postgres_data`는 남는다. 프로젝트 이름을 빠뜨렸다면 이 명령이 개발 데이터를 지우므로,
실행 전에 아래로 어떤 볼륨이 지워질지 먼저 확인한다.

```powershell
docker volume ls --filter name=recflow
```

Expected: `recflow_postgres_data`(개발)와 `recflow-prod_postgres_data`(운영)가 **둘 다** 보인다.
운영 볼륨이 없고 개발 볼륨만 있으면 프로젝트 이름이 적용되지 않은 것이므로 `down -v`를 실행하지 말 것.

- [ ] **Step 11: 개발 데이터 확인**

```powershell
Start-Sleep -Seconds 8
docker exec recflow-db psql -U recflow -d recflow -t -A -c "SELECT COUNT(*) FROM rec_market;"
```

Expected: 939. 로컬 개발 데이터가 그대로 남아 있어야 한다. 0이 나오면 개발 볼륨을 지운 것이므로 계획 A의 백필을 다시 실행해야 한다.

- [ ] **Step 12: 커밋**

검증만 했으므로 코드 변경이 없다. 변경이 있었다면 그 내용으로 커밋한다.

```powershell
git status --short
```

변경이 없으면 이 Task는 커밋 없이 넘어간다.

---

### Task 5: 배포 문서

**Files:**
- Create: `docs/deployment.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: Task 1~4 전부
- Produces: 사람이 따라 할 수 있는 VPS 배포 절차

- [ ] **Step 1: `docs/deployment.md` 작성**

````markdown
# RECFlow 배포 가이드

Ubuntu LTS VPS에 Docker Compose로 배포한다. 이 문서는 사람이 SSH로 수행하는 절차다.

---

## 1. VPS 초기 설정

### 1.1 사용자와 SSH

```bash
# root로 최초 접속한 뒤
adduser recflow
usermod -aG sudo recflow

# 로컬에서 공개키를 올린다
ssh-copy-id recflow@<VPS_IP>
```

`/etc/ssh/sshd_config`를 아래로 바꾸고 `sudo systemctl restart ssh`.

```text
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
```

> 재시작 전에 **새 터미널로 키 로그인이 되는지 먼저 확인**한다. 확인 없이 재시작했다가
> 키 설정이 잘못되어 있으면 접속 경로가 사라진다.

### 1.2 방화벽

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

`5432`와 `8000`을 열지 않는다. PostgreSQL과 수집기는 Docker 내부망에만 있어야 한다.

### 1.3 Docker

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker recflow
# 다시 로그인해서 그룹을 적용한다
docker --version
docker compose version
```

---

## 2. DNS

도메인 관리 화면에서 A 레코드를 만든다.

| 이름 | 타입 | 값 |
|---|---|---|
| `rec` | A | `<VPS_IP>` |

전파를 확인한다.

```bash
dig +short rec.<회사도메인>
```

VPS IP가 나와야 한다. **DNS가 맞기 전에 Caddy를 띄우면 Let's Encrypt 발급이 실패하고
일정 시간 재시도가 제한된다.** 반드시 먼저 확인한다.

---

## 3. 코드와 환경변수

```bash
sudo mkdir -p /opt/recflow
sudo chown recflow:recflow /opt/recflow
cd /opt
git clone https://github.com/gnghkim/RECFlow.git recflow
cd /opt/recflow

cp .env.prod.example .env
```

`.env`를 열어 값을 채운다. 비밀번호와 키는 직접 생성한다.

```bash
openssl rand -base64 32   # POSTGRES_PASSWORD
openssl rand -base64 32   # AUTH_SECRET
openssl rand -base64 24   # APP_PASSWORD
```

반드시 확인할 것:

- `RECFLOW_DOMAIN`이 실제 도메인과 같은가
- `DATABASE_URL`의 비밀번호가 `POSTGRES_PASSWORD`와 **같은 값**인가
- `AUTH_SECRET`이 32자 이상인가

```bash
chmod 600 .env
```

---

## 4. 최초 기동

### 4.1 공유 네트워크

```bash
docker network create edge
```

향후 다른 사내 서비스도 이 네트워크에 합류시킨다.

### 4.2 빌드와 기동

```bash
cd /opt/recflow
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
```

다섯 서비스가 모두 `Up`이고 `db`가 `healthy`인지 본다.

### 4.3 스키마 적용

DB 포트가 닫혀 있으므로 컨테이너 안에서 실행한다.

```bash
docker run --rm --network recflow-internal \
  -v /opt/recflow/prisma:/prisma \
  -e DATABASE_URL="$(grep '^DATABASE_URL=' /opt/recflow/.env | cut -d= -f2-)" \
  node:24-slim sh -c "npm i -g prisma@6.19.3 && prisma migrate deploy --schema /prisma/schema.prisma"
```

확인:

```bash
docker compose -f docker-compose.prod.yml exec db psql -U recflow -d recflow -c "\dt"
```

테이블 8개가 보여야 한다.

### 4.4 HTTPS 확인

```bash
docker compose -f docker-compose.prod.yml logs caddy --tail 30
curl -I https://rec.<회사도메인>/login
```

Caddy 로그에 인증서 발급 성공이 보이고 `200`이 나와야 한다.

---

## 5. 데이터 적재

### 5.1 API 키가 있을 때

```bash
# 실제 응답 필드 확인
docker compose -f docker-compose.prod.yml exec collector python -m cli probe --date 20260813

# 필드가 다르면 apps/collector/rec/mapping.py 수정 후 재빌드
docker compose -f docker-compose.prod.yml up -d --build collector

# 과거 데이터 백필. 개발계정은 하루 100건 제한이라 며칠에 나뉜다.
docker compose -f docker-compose.prod.yml exec collector \
  python -m cli backfill --from 20230815 --to 20260813 --source api
```

예산이 소진되면 자동으로 멈추고 다음 실행에서 이어받는다. 매일 09:00 누락일 점검이
남은 구간을 계속 채운다.

### 5.2 API 키가 아직 없을 때

수집기는 `KPX_API_KEY`가 비어 있으면 fixture 소스로 뜬다. 화면 확인용으로는 쓸 수 있지만
**실제 시세가 아니다.** 운영에서는 키 발급 전까지 데이터를 넣지 않는 편이 낫다. fixture와
실데이터가 섞이면 나중에 구분하기 어렵다. 구분이 필요하면 `rec_market.source` 열을 본다.

---

## 6. 운영

### 6.1 상태 확인

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs collector --tail 50
docker stats --no-stream
df -h
```

웹의 `/admin` 화면에서 마지막 수집 시각과 최근 실행 이력을 볼 수 있다.

### 6.2 배포 갱신

```bash
cd /opt/recflow
git pull
docker compose -f docker-compose.prod.yml up -d --build

# 스키마 변경이 있었다면
docker run --rm --network recflow-internal \
  -v /opt/recflow/prisma:/prisma \
  -e DATABASE_URL="$(grep '^DATABASE_URL=' .env | cut -d= -f2-)" \
  node:24-slim sh -c "npm i -g prisma@6.19.3 && prisma migrate deploy --schema /prisma/schema.prisma"
```

### 6.3 백업

매일 02:00에 자동 실행된다.

```bash
ls -lh /opt/recflow/infra/backup/dumps/daily
docker compose -f docker-compose.prod.yml logs db-backup --tail 20

# 수동 실행
docker compose -f docker-compose.prod.yml exec db-backup /usr/local/bin/backup.sh
```

보관: 일별 7 / 주별 4 / 월별 12.

**복구가 실제로 되는지 반년에 한 번은 확인한다.** 한 번도 복구해보지 않은 백업은
백업이 아니다. 확인은 운영 DB가 아니라 별도 데이터베이스에 넣어본다.

```bash
docker compose -f docker-compose.prod.yml exec db createdb -U recflow recflow_restore_test
gunzip -c infra/backup/dumps/daily/<파일>.sql.gz | \
  docker compose -f docker-compose.prod.yml exec -T db psql -U recflow -d recflow_restore_test
docker compose -f docker-compose.prod.yml exec db psql -U recflow -d recflow_restore_test -c "SELECT COUNT(*) FROM rec_market;"
docker compose -f docker-compose.prod.yml exec db dropdb -U recflow recflow_restore_test
```

### 6.4 복구

```bash
cd /opt/recflow
./infra/scripts/restore.sh infra/backup/dumps/daily/<파일>.sql.gz
```

웹과 수집기를 멈춘 뒤 복구하고 다시 띄운다.

---

## 7. 외부 백업 복제 (미구현, 권장)

현재 백업은 VPS 안에만 있다. **VPS 자체가 사라지면 백업도 함께 사라진다.**
REC 가격 이력은 화·목에만 생성되어 다시 만들 수 없으므로 외부 복제를 권장한다.

선택지:

- Cloudflare R2 또는 S3 호환 스토리지에 `rclone`으로 일 1회 동기화
- 별도 NAS나 다른 VPS로 `rsync`
- 관리자 PC로 주 1회 수동 내려받기

가장 단순한 시작은 마지막 방법이다. 자동화보다 **실제로 하는 것**이 중요하다.

---

## 8. 보안 점검표

배포 후 확인한다.

- [ ] SSH 비밀번호 로그인 차단, 키 로그인만 동작
- [ ] root 직접 로그인 차단
- [ ] UFW에서 22/80/443만 열림
- [ ] `ss -tlnp`에 5432와 8000이 **없음**
- [ ] `docker compose -f docker-compose.prod.yml ps`에서 caddy만 포트 매핑
- [ ] HTTPS 접속, HTTP는 리다이렉트
- [ ] `.env` 권한 600, git에 없음
- [ ] 웹 접속 시 로그인 요구
- [ ] 잘못된 비밀번호 6회 시 429

```bash
ss -tlnp | grep -E '5432|8000'   # 아무것도 안 나와야 정상
```

---

## 9. 문제 해결

| 증상 | 확인 |
|---|---|
| HTTPS 인증서 발급 실패 | `dig +short rec.<도메인>`이 VPS IP인가. 80 포트가 열려 있는가 |
| 웹이 502 | `docker compose logs web`. `DATABASE_URL` 비밀번호가 `POSTGRES_PASSWORD`와 같은가 |
| 로그인이 안 됨 | `.env`의 `APP_PASSWORD`와 `AUTH_SECRET`(32자 이상) 확인 후 `up -d web` |
| `/admin`이 수집기 연결 불가 | `docker compose logs collector`. `COLLECTOR_INTERNAL_URL`이 `http://collector:8000`인가 |
| 화면 숫자가 안 바뀜 | `app/(app)/layout.tsx`의 `force-dynamic`이 지워졌는지 확인 |
| 수집이 안 돎 | 화·목이 아니면 정상이다. `/admin`의 최근 실행 이력과 `collection_runs`를 본다 |
| 디스크 부족 | `docker system prune -a`, 오래된 덤프 정리 |
````

- [ ] **Step 2: README 갱신**

`README.md`의 현재 상태 표에서 계획 C를 **완료**로 바꾸고, 문서 목록에 배포 가이드를 추가한다.

```markdown
| 계획 C | 배포 — 운영 compose, Caddy, 자동백업 | **완료** |
```

문서 절에 추가:

```markdown
- [배포 가이드](docs/deployment.md) — VPS 초기 설정부터 배포·백업·복구까지
```

"시작하기" 절 끝에 운영 배포 안내를 한 줄 넣는다.

```markdown
### 운영 배포

VPS 배포는 [배포 가이드](docs/deployment.md)를 따른다. 운영은 `docker-compose.prod.yml`을
쓰며 Caddy가 HTTPS를 맡는다. 웹만 외부에 노출되고 DB와 수집기는 내부망에만 있다.
```

- [ ] **Step 3: 커밋**

```powershell
git add docs/deployment.md README.md
git commit -m "docs: VPS 배포 가이드 추가

SSH 잠금부터 DNS, 최초 기동, 스키마 적용, 백업 복구까지 사람이 따라 할
절차로 적었다.

DNS 전파를 먼저 확인하라고 명시했다. 확인 전에 Caddy를 띄우면
Let's Encrypt 발급이 실패하고 재시도가 제한된다.

복구를 반년에 한 번 실제로 해보라고 적었다. 한 번도 복구해보지 않은
백업은 백업이 아니다. 외부 복제가 아직 없다는 사실도 명시했다."
```

---

## 완료 기준

계획 C는 아래가 모두 참일 때 완료된다.

1. `docker build -f apps/web/Dockerfile -t recflow-web:test .`가 성공한다.
2. 웹 컨테이너가 DB 없이도 기동하고 `/login`이 200을 반환한다.
3. `docker compose -f docker-compose.prod.yml config`에서 `published` 포트가 **caddy에만** 있다.
4. 로컬에서 운영 스택 5개가 전부 뜨고, 호스트의 5432·8000·3000이 **닫혀 있다**.
5. 웹 컨테이너가 `http://collector:8000/health`에 도달한다.
6. 백업 스크립트가 실제 덤프를 만들고, 그 덤프에 `rec_market`의 `CREATE TABLE`과 데이터가 들어 있다.
7. 보관정책이 오래된 파일을 실제로 지운다.
8. **검증 후 로컬 개발 DB의 `rec_market`이 939행 그대로다.** 0이면 프로젝트 이름 분리를 빠뜨려 개발 볼륨을 지운 것이다.
9. `docs/deployment.md`만 보고 배포할 수 있다.

## 계획 C에서 하지 않는 것

- 실제 VPS 배포 (사람이 SSH로 수행)
- 백업 외부 복제 구현 (문서에 절차만)
- CI/CD 파이프라인
- 모니터링·알림 스택
- SMP, Telegram 알림 (Phase 4)
