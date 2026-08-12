# 계획 A — REC 데이터 파이프라인 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** REC 현물시장 데이터를 수집·검증·적재하여 PostgreSQL에 축적하는 파이프라인을 구축한다. API 키가 없는 현재는 fixture 소스로 동작하고, 키가 발급되면 `mapping.py` 한 파일만 고쳐 실 API로 전환된다.

**Architecture:** Python collector가 `client`(HTTP) → `mapping`(필드 변환) → `service`(조립) → `repository`(UPSERT) 순으로 흐른다. 각 모듈은 도메인 dataclass로만 대화하며, API 응답 필드명을 아는 파일은 `mapping.py` 하나뿐이다. 스키마는 Prisma가 단독 소유하고 collector는 DDL을 실행하지 않는다.

**Tech Stack:** Python 3.12, psycopg 3, httpx, APScheduler 3, FastAPI, pytest / Node 22, Prisma 6 / PostgreSQL 16, Docker Compose

**설계문서:** `docs/superpowers/specs/2026-08-12-rec-price-tracker-design.md` — 충돌 시 설계문서가 우선한다.

---

## Global Constraints

- 작업 디렉토리는 `C:\Dev\RECFlow`. 이미 git 저장소이며 브랜치는 `main`이다.
- 개발 호스트는 **Windows 11 + PowerShell**. Docker Desktop이 설치되어 있으나 정지 상태일 수 있으므로 먼저 기동해야 한다.
- **Python 코드는 컨테이너(python:3.12-slim) 안에서 실행하고 테스트한다.** 호스트에는 Python 3.14만 설치되어 있어 `psycopg[binary]` 등의 휠이 없을 수 있다. 호스트에 가상환경을 만들지 말 것. 표준 테스트 명령은 다음 하나뿐이다.

  ```powershell
  docker compose run --rm collector-test
  ```
- **Prisma가 스키마의 단독 소유자.** Python 코드는 `CREATE`/`ALTER`/`DROP` 등 어떤 DDL도 실행하지 않는다. 테이블은 항상 Prisma 마이그레이션으로만 만든다.
- **API 응답 필드명을 아는 파일은 `apps/collector/rec/mapping.py` 하나뿐이다.** 다른 어떤 파일에도 API 필드 문자열을 쓰지 않는다.
- 가격·수량·금액은 전부 `decimal.Decimal`(PostgreSQL `numeric`). Python `float`을 쓰지 않는다.
- 타임존은 `Asia/Seoul`로 고정한다. 컨테이너 환경변수 `TZ=Asia/Seoul`.
- 비밀값은 `.env`로만 관리하고 절대 커밋하지 않는다. `.env.example`만 커밋한다.
- 루트 `package.json`이 Prisma 도구와 마이그레이션 스크립트를 소유한다.
- DB 이름은 `recflow`, 사용자는 `recflow`.
- 이번 계획에서 **SMP, alerts, Telegram, 웹 UI는 만들지 않는다.**
- 각 Task는 마지막에 커밋으로 끝난다. 커밋 메시지는 한국어 본문 + Conventional Commits 접두사.

### 확정되지 않은 사실 (중요)

공공데이터포털 「한국전력거래소_REC 현물시장 정보」 API의 **응답 item 필드 영문명은 아직 확인되지 않았다.** API 키가 없어 실제 호출이 불가능하다.

이 계획에서 사용하는 필드명은 **잠정값**이며, `mapping.py`의 `FIELD_MAP` 상수 한 곳에 모아둔다. 키 발급 후 `probe` 명령으로 실제 응답을 덤프하여 이 상수만 고친다. 잠정 필드명을 `mapping.py` 밖의 어떤 파일에도 퍼뜨리지 말 것.

확인된 사실(변경 금지):
- 요청 변수: `serviceKey`, `pageNo`, `numOfRows`, `dataType`, `tradeDay`
- 개발계정 트래픽 100건/일
- 종가·거래금액은 육지·제주 통합값으로만 제공된다

---

## File Structure

| 파일 | 책임 |
|---|---|
| `package.json` | 리포 루트. Prisma 도구와 스크립트 소유 |
| `apps/collector/Dockerfile` | 앱 구동과 테스트에 공용으로 쓰는 python:3.12 이미지 |
| `prisma/schema.prisma` | 전체 DB 스키마의 단독 정의 |
| `docker-compose.yml` | 로컬 개발용 db / collector |
| `.env.example` | 환경변수 목록 |
| `apps/collector/rec/models.py` | 도메인 dataclass. 외부 의존 없음 |
| `apps/collector/rec/mapping.py` | **API 응답 → 도메인 변환. 필드명을 아는 유일한 파일** |
| `apps/collector/rec/client.py` | HTTP 호출, 재시도, 타임아웃, 일일 예산 |
| `apps/collector/rec/fixture_client.py` | fixture 파일 읽기. `client`와 동일 인터페이스 |
| `apps/collector/rec/repository.py` | SQL. UPSERT, 원본저장, 실행이력 |
| `apps/collector/rec/service.py` | 위 모듈 조립 |
| `apps/collector/rec/validation.py` | 도메인 값 검증 규칙 |
| `apps/collector/jobs/scheduler.py` | APScheduler 등록 |
| `apps/collector/api.py` | 내부 전용 FastAPI |
| `apps/collector/cli.py` | probe / collect / backfill / gen-fixture |
| `apps/collector/tests/` | pytest |

---

### Task 1: 리포 기반과 로컬 PostgreSQL

**Files:**
- Create: `package.json`
- Create: `.env.example`
- Create: `docker-compose.yml`
- Create: `README.md`

**Interfaces:**
- Consumes: 없음 (최초 Task)
- Produces: `postgresql://recflow:<password>@localhost:5432/recflow` 로 접근 가능한 로컬 DB. 이후 모든 Task가 이 DSN을 `DATABASE_URL`로 사용한다.

- [ ] **Step 1: 루트 `package.json` 작성**

`workspaces` 키는 지금 넣지 않는다. `apps/web`이 아직 없어 `npm install`이 실패한다. 계획 B에서 `apps/web`을 만들 때 추가한다.

```json
{
  "name": "recflow",
  "private": true,
  "version": "0.1.0",
  "scripts": {
    "db:migrate": "prisma migrate dev --schema prisma/schema.prisma",
    "db:deploy": "prisma migrate deploy --schema prisma/schema.prisma",
    "db:generate": "prisma generate --schema prisma/schema.prisma",
    "db:studio": "prisma studio --schema prisma/schema.prisma"
  },
  "devDependencies": {
    "prisma": "^6.1.0"
  },
  "dependencies": {
    "@prisma/client": "^6.1.0"
  }
}
```

- [ ] **Step 2: `.env.example` 작성**

```text
# --- Database ---
POSTGRES_DB=recflow
POSTGRES_USER=recflow
POSTGRES_PASSWORD=change-me-in-real-env
DATABASE_URL=postgresql://recflow:change-me-in-real-env@localhost:5432/recflow

# --- KPX Open API ---
# 공공데이터포털에서 발급받은 일반 인증키(Decoding). 미발급 상태면 비워둔다.
KPX_API_KEY=
KPX_BASE_URL=https://apis.data.go.kr/B552115/RecMarketInfo2
# 개발계정 한도 100건/일 대비 안전 마진
KPX_DAILY_BUDGET=80

# --- Collector ---
TZ=Asia/Seoul
COLLECTOR_PORT=8000
```

- [ ] **Step 3: 실제 `.env` 생성 (커밋하지 않음)**

```powershell
Copy-Item C:\Dev\RECFlow\.env.example C:\Dev\RECFlow\.env
```

`.env` 안의 `change-me-in-real-env`를 임의의 로컬 비밀번호로 바꾸고, `POSTGRES_PASSWORD`와 `DATABASE_URL` 두 곳을 **같은 값**으로 맞춘다. `.gitignore`에 이미 `.env`가 등록되어 있으므로 커밋되지 않는다.

- [ ] **Step 4: `docker-compose.yml` 작성**

```yaml
services:
  db:
    image: postgres:16-alpine
    container_name: recflow-db
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      TZ: ${TZ}
    ports:
      # 로컬 개발 편의를 위해서만 노출한다. 운영 compose에서는 노출하지 않는다.
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 10

volumes:
  postgres_data:
```

`collector` 서비스는 Task 9에서 추가한다. 지금 추가하면 Dockerfile이 없어 기동이 실패한다.

- [ ] **Step 5: Docker Desktop 기동 후 DB 실행**

```powershell
docker compose --project-directory C:\Dev\RECFlow up -d db
```

Docker Desktop이 꺼져 있으면 먼저 실행하고 엔진이 올라올 때까지 기다린 뒤 재시도한다.

- [ ] **Step 6: DB 연결 검증**

```powershell
docker exec recflow-db psql -U recflow -d recflow -c "SELECT version();"
```

Expected: `PostgreSQL 16.x ...` 한 줄이 출력된다. 실패하면 `docker compose logs db`로 원인을 확인한다.

- [ ] **Step 7: `README.md` 작성**

```markdown
# RECFlow

법인 보유 태양광 REC의 시장가격을 자동 추적하고 매각 의사결정을 지원하는 사내 웹 시스템.

- 설계문서: `docs/superpowers/specs/2026-08-12-rec-price-tracker-design.md`
- 구현계획: `docs/superpowers/plans/`

## 로컬 개발 준비

1. Docker Desktop을 실행한다.
2. `.env.example`을 `.env`로 복사하고 비밀번호를 채운다.
3. DB를 띄운다.

   ```powershell
   docker compose up -d db
   ```

4. 스키마를 적용한다.

   ```powershell
   npm install
   npm run db:migrate
   ```

## 구성

| 디렉토리 | 내용 |
|---|---|
| `prisma/` | DB 스키마 단독 정의 |
| `apps/collector/` | Python 수집기 |
| `apps/web/` | Next.js 웹 (계획 B) |
| `infra/` | Caddy, 백업 스크립트 (계획 C) |
```

- [ ] **Step 8: 커밋**

```powershell
git add package.json .env.example docker-compose.yml README.md
git commit -m "chore: 로컬 개발 기반 구성

npm workspaces 루트, 환경변수 예시, 로컬 PostgreSQL 16 compose를 추가했다.
DB 포트 노출은 로컬 개발 전용이며 운영 compose에서는 노출하지 않는다."
```

---

### Task 2: Prisma 스키마와 최초 마이그레이션

**Files:**
- Create: `prisma/schema.prisma`
- Create: `prisma/migrations/` (Prisma가 생성)

**Interfaces:**
- Consumes: Task 1의 `DATABASE_URL`
- Produces: 테이블 `rec_market`, `rec_market_raw`, `collection_runs`, `plants`, `rec_inventory`, `rec_sales`, `price_targets`. 이후 collector의 `repository.py`가 이 테이블명과 컬럼명(snake_case)에 SQL로 접근한다.

- [ ] **Step 1: `prisma/schema.prisma` 작성**

`@@map`과 `@map`으로 DB 실제 이름을 snake_case로 고정한다. Python이 SQL로 직접 접근하므로 이름이 흔들리면 안 된다.

```prisma
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

enum MarketArea {
  LAND
  JEJU
  TOTAL
}

enum CollectionJobType {
  SCHEDULED
  RECHECK
  BACKFILL
  MANUAL
  GAP_SCAN
}

enum CollectionStatus {
  SUCCESS
  PARTIAL
  NO_DATA
  FAILED
}

/// REC 현물시장 거래일별 시세
model RecMarket {
  id          Int        @id @default(autoincrement())
  tradeDate   DateTime   @map("trade_date") @db.Date
  marketArea  MarketArea @map("market_area")
  tradeCount  Int?       @map("trade_count")
  volume      Decimal?   @db.Decimal(14, 2)
  avgPrice    Decimal?   @map("avg_price") @db.Decimal(12, 2)
  highPrice   Decimal?   @map("high_price") @db.Decimal(12, 2)
  lowPrice    Decimal?   @map("low_price") @db.Decimal(12, 2)
  /// 종가는 육지·제주 통합값으로만 제공되므로 TOTAL 행에만 채워진다
  closePrice  Decimal?   @map("close_price") @db.Decimal(12, 2)
  /// 거래금액도 통합값으로만 제공된다
  tradeAmount Decimal?   @map("trade_amount") @db.Decimal(18, 2)
  source      String     @db.VarChar(32)
  createdAt   DateTime   @default(now()) @map("created_at")
  updatedAt   DateTime   @updatedAt @map("updated_at")

  @@unique([tradeDate, marketArea], name: "rec_market_trade_date_market_area_key")
  @@index([tradeDate])
  @@map("rec_market")
}

/// API 원본 응답 보존. 매핑보다 먼저 저장한다.
model RecMarketRaw {
  id              Int            @id @default(autoincrement())
  tradeDate       DateTime       @map("trade_date") @db.Date
  endpoint        String         @db.VarChar(255)
  httpStatus      Int            @map("http_status")
  payload         Json
  fetchedAt       DateTime       @default(now()) @map("fetched_at")
  collectionRunId Int?           @map("collection_run_id")
  collectionRun   CollectionRun? @relation(fields: [collectionRunId], references: [id], onDelete: SetNull)

  @@index([tradeDate])
  @@map("rec_market_raw")
}

/// 수집 실행 이력. 운영 모니터링과 누락일 탐지의 근거.
model CollectionRun {
  id           Int               @id @default(autoincrement())
  jobType      CollectionJobType @map("job_type")
  targetDate   DateTime?         @map("target_date") @db.Date
  status       CollectionStatus
  attempts     Int               @default(0)
  rowsUpserted Int               @default(0) @map("rows_upserted")
  errorMessage String?           @map("error_message")
  startedAt    DateTime          @default(now()) @map("started_at")
  finishedAt   DateTime?         @map("finished_at")

  raws RecMarketRaw[]

  @@index([targetDate])
  @@index([startedAt])
  @@map("collection_runs")
}

/// 발전소
model Plant {
  id            Int       @id @default(autoincrement())
  name          String    @db.VarChar(120)
  location      String?   @db.VarChar(200)
  capacityKw    Decimal?  @map("capacity_kw") @db.Decimal(12, 2)
  operationDate DateTime? @map("operation_date") @db.Date
  /// 참고값. 평가액 계산에 사용하지 않는다.
  recWeight     Decimal?  @map("rec_weight") @db.Decimal(4, 2)
  isActive      Boolean   @default(true) @map("is_active")
  createdAt     DateTime  @default(now()) @map("created_at")
  updatedAt     DateTime  @updatedAt @map("updated_at")

  inventories RecInventory[]
  sales       RecSale[]

  @@map("plants")
}

/// REC 발급 이력. rec_quantity는 가중치가 이미 적용된 수량이다.
model RecInventory {
  id          Int       @id @default(autoincrement())
  plantId     Int       @map("plant_id")
  issueDate   DateTime  @map("issue_date") @db.Date
  recQuantity Decimal   @map("rec_quantity") @db.Decimal(14, 2)
  /// 소멸 처리일. NULL이면 유효한 발급분이다.
  expiredAt   DateTime? @map("expired_at") @db.Date
  memo        String?
  createdAt   DateTime  @default(now()) @map("created_at")
  updatedAt   DateTime  @updatedAt @map("updated_at")

  plant Plant @relation(fields: [plantId], references: [id], onDelete: Restrict)

  @@index([plantId])
  @@index([issueDate])
  @@map("rec_inventory")
}

/// 실제 매각 내역
model RecSale {
  id         Int      @id @default(autoincrement())
  plantId    Int      @map("plant_id")
  saleDate   DateTime @map("sale_date") @db.Date
  quantity   Decimal  @db.Decimal(14, 2)
  unitPrice  Decimal  @map("unit_price") @db.Decimal(12, 2)
  /// 실제 정산금액. 기본값은 quantity * unit_price이나 반올림 차이를 허용한다.
  saleAmount Decimal  @map("sale_amount") @db.Decimal(18, 2)
  buyer      String?  @db.VarChar(120)
  memo       String?
  createdAt  DateTime @default(now()) @map("created_at")

  plant Plant @relation(fields: [plantId], references: [id], onDelete: Restrict)

  @@index([plantId])
  @@index([saleDate])
  @@map("rec_sales")
}

/// 목표가격. 이번 범위에서는 표시·시뮬레이션 기준값으로만 쓰인다.
model PriceTarget {
  id          Int      @id @default(autoincrement())
  name        String   @db.VarChar(120)
  targetPrice Decimal  @map("target_price") @db.Decimal(12, 2)
  isActive    Boolean  @default(true) @map("is_active")
  createdAt   DateTime @default(now()) @map("created_at")
  updatedAt   DateTime @updatedAt @map("updated_at")

  @@map("price_targets")
}
```

- [ ] **Step 2: 의존성 설치**

```powershell
cd C:\Dev\RECFlow
npm install
```

- [ ] **Step 3: 마이그레이션 생성 및 적용**

```powershell
npm run db:migrate -- --name init
```

Expected: `prisma/migrations/<timestamp>_init/migration.sql`이 생성되고 "Your database is now in sync with your schema."가 출력된다.

- [ ] **Step 4: 테이블 생성 검증**

```powershell
docker exec recflow-db psql -U recflow -d recflow -c "\dt"
```

Expected: `collection_runs`, `plants`, `price_targets`, `rec_inventory`, `rec_market`, `rec_market_raw`, `rec_sales`, `_prisma_migrations` 총 8개가 보인다.

- [ ] **Step 5: UNIQUE 제약 검증**

```powershell
docker exec recflow-db psql -U recflow -d recflow -c "\d rec_market"
```

Expected: 인덱스 목록에 `rec_market_trade_date_market_area_key` UNIQUE가 있다. 이 제약이 없으면 이후 UPSERT가 동작하지 않으므로 반드시 확인한다.

- [ ] **Step 6: 커밋**

```powershell
git add prisma package-lock.json
git commit -m "feat: Prisma 스키마와 최초 마이그레이션 추가

시장 데이터(rec_market, rec_market_raw, collection_runs)와
회사 데이터(plants, rec_inventory, rec_sales, price_targets)를 분리했다.

rec_inventory에는 status 컬럼을 두지 않는다. 보유량은
발급(미소멸) 합계에서 매각 합계를 빼는 파생 계산으로 구한다.
부분 매각을 표현할 수 없고 rec_sales와 이중 기록되는 문제를 피하기 위함이다."
```

---

### Task 3: 도메인 모델과 API 매핑

**Files:**
- Create: `apps/collector/pyproject.toml`
- Create: `apps/collector/requirements.txt`
- Create: `apps/collector/requirements-dev.txt`
- Create: `apps/collector/Dockerfile`
- Create: `apps/collector/.dockerignore`
- Modify: `docker-compose.yml` (테스트 실행 서비스 추가)
- Create: `apps/collector/rec/__init__.py`
- Create: `apps/collector/rec/models.py`
- Create: `apps/collector/rec/mapping.py`
- Create: `apps/collector/tests/__init__.py`
- Create: `apps/collector/tests/test_mapping.py`
- Create: `apps/collector/tests/samples/rec_response_sample.json`

**Interfaces:**
- Consumes: 없음 (순수 Python)
- Produces:
  - `MarketArea` (StrEnum): `LAND` / `JEJU` / `TOTAL`
  - `RecMarketRow` (frozen dataclass): `trade_date: date`, `market_area: MarketArea`, `trade_count: int | None`, `volume: Decimal | None`, `avg_price: Decimal | None`, `high_price: Decimal | None`, `low_price: Decimal | None`, `close_price: Decimal | None`, `trade_amount: Decimal | None`
  - `ApiResponse` (frozen dataclass): `trade_date: date`, `payload: dict`, `http_status: int`, `endpoint: str`
  - `map_response(response: ApiResponse) -> list[RecMarketRow]`
  - `MappingError(Exception)`

- [ ] **Step 1: 파이썬 프로젝트 파일 작성**

`apps/collector/requirements.txt`:

```text
httpx==0.28.1
psycopg[binary]==3.2.3
APScheduler==3.11.0
fastapi==0.115.6
uvicorn[standard]==0.34.0
python-dotenv==1.0.1
```

`apps/collector/requirements-dev.txt`:

```text
-r requirements.txt
pytest==8.3.4
respx==0.22.0
```

`apps/collector/pyproject.toml`:

```toml
[project]
name = "recflow-collector"
version = "0.1.0"
requires-python = ">=3.12"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 2: Dockerfile과 테스트 실행 환경 준비**

호스트에는 Python 3.14만 있어 `psycopg[binary]` 휠이 없을 수 있다. 파이썬은 처음부터 컨테이너 안에서만 돌린다.

`apps/collector/Dockerfile`:

```dockerfile
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Seoul

WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
# 개발 의존성까지 설치한다. 같은 이미지를 앱 구동과 테스트에 모두 쓴다.
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "api:build_default_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
```

`apps/collector/.dockerignore`:

```text
__pycache__/
.pytest_cache/
fixtures/
```

fixture는 컨테이너 안에서 다시 생성할 수 있으므로 이미지에 넣지 않는다. `tests/`는 컨테이너에서 테스트를 돌리므로 **제외하지 않는다.**

`docker-compose.yml`의 `services:` 아래에 테스트 실행 서비스를 추가한다.

```yaml
  collector-test:
    build: ./apps/collector
    profiles: ["dev"]
    depends_on:
      db:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
      TZ: ${TZ}
    volumes:
      # 소스를 마운트해 이미지 재빌드 없이 테스트를 반복한다.
      - ./apps/collector:/app
    command: ["python", "-m", "pytest", "-v"]
```

`profiles: ["dev"]`가 있으므로 `docker compose up`에서는 뜨지 않고 `docker compose run`으로만 실행된다.

- [ ] **Step 2b: 이미지 빌드 확인**

```powershell
cd C:\Dev\RECFlow
docker compose build collector-test
```

Expected: 빌드 성공. 이후 모든 테스트는 다음 한 줄로 실행한다.

```powershell
docker compose run --rm collector-test
```

특정 파일만 돌리려면 명령을 덧붙인다.

```powershell
docker compose run --rm collector-test python -m pytest tests/test_mapping.py -v
```

- [ ] **Step 3: 샘플 응답 fixture 작성**

`apps/collector/tests/samples/rec_response_sample.json` — 공공데이터포털 표준 JSON 봉투 구조를 따른다. **item 필드명은 잠정값이며 probe로 확정한다.**

```json
{
  "response": {
    "header": { "resultCode": "00", "resultMsg": "NORMAL SERVICE." },
    "body": {
      "numOfRows": 10,
      "pageNo": 1,
      "totalCount": 3,
      "items": {
        "item": [
          {
            "tradeDay": "20260806",
            "areaCd": "육지",
            "tradeCnt": "412",
            "tradeQty": "185000",
            "avgPrice": "71500",
            "highPrice": "72300",
            "lowPrice": "70800",
            "closePrice": "",
            "tradeAmt": ""
          },
          {
            "tradeDay": "20260806",
            "areaCd": "제주",
            "tradeCnt": "38",
            "tradeQty": "9500",
            "avgPrice": "70900",
            "highPrice": "71400",
            "lowPrice": "70200",
            "closePrice": "",
            "tradeAmt": ""
          },
          {
            "tradeDay": "20260806",
            "areaCd": "합계",
            "tradeCnt": "450",
            "tradeQty": "194500",
            "avgPrice": "71450",
            "highPrice": "72300",
            "lowPrice": "70200",
            "closePrice": "71600",
            "tradeAmt": "13897550000"
          }
        ]
      }
    }
  }
}
```

- [ ] **Step 4: 실패하는 테스트 작성**

`apps/collector/tests/test_mapping.py`:

```python
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from rec.mapping import MappingError, map_response
from rec.models import ApiResponse, MarketArea

SAMPLES = Path(__file__).parent / "samples"


def load_sample() -> ApiResponse:
    payload = json.loads((SAMPLES / "rec_response_sample.json").read_text(encoding="utf-8"))
    return ApiResponse(
        trade_date=date(2026, 8, 6),
        payload=payload,
        http_status=200,
        endpoint="https://example.test/RecMarketInfo2",
    )


def test_maps_three_area_rows():
    rows = map_response(load_sample())
    assert len(rows) == 3
    assert {r.market_area for r in rows} == {MarketArea.LAND, MarketArea.JEJU, MarketArea.TOTAL}


def test_total_row_carries_close_price_and_trade_amount():
    rows = map_response(load_sample())
    total = next(r for r in rows if r.market_area is MarketArea.TOTAL)
    assert total.close_price == Decimal("71600")
    assert total.trade_amount == Decimal("13897550000")
    assert total.avg_price == Decimal("71450")
    assert total.trade_count == 450


def test_land_row_has_no_close_price():
    """종가와 거래금액은 통합값으로만 제공되므로 육지 행에서는 None이어야 한다."""
    rows = map_response(load_sample())
    land = next(r for r in rows if r.market_area is MarketArea.LAND)
    assert land.close_price is None
    assert land.trade_amount is None
    assert land.volume == Decimal("185000")


def test_uses_decimal_not_float():
    rows = map_response(load_sample())
    total = next(r for r in rows if r.market_area is MarketArea.TOTAL)
    assert isinstance(total.avg_price, Decimal)


def test_trade_date_comes_from_payload_not_request():
    """요청한 날짜가 아니라 응답 본문의 거래일을 신뢰한다."""
    rows = map_response(load_sample())
    assert all(r.trade_date == date(2026, 8, 6) for r in rows)


def test_empty_items_returns_empty_list():
    """휴장일에는 item이 비어 온다. 예외가 아니라 빈 목록이다."""
    response = ApiResponse(
        trade_date=date(2026, 8, 5),
        payload={
            "response": {
                "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
                "body": {"numOfRows": 10, "pageNo": 1, "totalCount": 0, "items": ""},
            }
        },
        http_status=200,
        endpoint="https://example.test/RecMarketInfo2",
    )
    assert map_response(response) == []


def test_missing_field_raises_mapping_error_listing_available_keys():
    """필드명이 바뀌면 조용히 None이 되지 않고 실제 키 목록과 함께 실패해야 한다."""
    response = ApiResponse(
        trade_date=date(2026, 8, 6),
        payload={
            "response": {
                "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
                "body": {"items": {"item": [{"someOtherName": "20260806"}]}},
            }
        },
        http_status=200,
        endpoint="https://example.test/RecMarketInfo2",
    )
    with pytest.raises(MappingError) as exc:
        map_response(response)
    assert "someOtherName" in str(exc.value)


def test_api_error_result_code_raises():
    response = ApiResponse(
        trade_date=date(2026, 8, 6),
        payload={
            "response": {
                "header": {"resultCode": "30", "resultMsg": "SERVICE KEY IS NOT REGISTERED ERROR."},
                "body": {},
            }
        },
        http_status=200,
        endpoint="https://example.test/RecMarketInfo2",
    )
    with pytest.raises(MappingError) as exc:
        map_response(response)
    assert "30" in str(exc.value)
```

- [ ] **Step 5: 테스트가 실패하는지 확인**

```powershell
cd C:\Dev\RECFlow
docker compose run --rm collector-test python -m pytest tests/test_mapping.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'rec'`

- [ ] **Step 6: `rec/models.py` 구현**

```python
"""도메인 모델. 외부 라이브러리와 API 필드명을 알지 못한다."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum


class MarketArea(StrEnum):
    LAND = "LAND"
    JEJU = "JEJU"
    TOTAL = "TOTAL"


@dataclass(frozen=True, slots=True)
class ApiResponse:
    """수집 소스가 돌려주는 원본 응답. client와 fixture_client의 공통 반환형."""

    trade_date: date
    payload: dict
    http_status: int
    endpoint: str


@dataclass(frozen=True, slots=True)
class RecMarketRow:
    """rec_market 한 행에 대응하는 도메인 값."""

    trade_date: date
    market_area: MarketArea
    trade_count: int | None = None
    volume: Decimal | None = None
    avg_price: Decimal | None = None
    high_price: Decimal | None = None
    low_price: Decimal | None = None
    close_price: Decimal | None = None
    trade_amount: Decimal | None = None
```

- [ ] **Step 7: `rec/mapping.py` 구현**

```python
"""API 응답을 도메인 모델로 옮긴다.

이 파일은 REC 현물시장 API의 응답 필드명을 아는 **유일한** 파일이다.
다른 어떤 모듈에도 API 필드 문자열을 쓰지 말 것.

주의: 아래 FIELD_MAP과 AREA_MAP의 값은 API 키 미발급 상태에서 정한 **잠정값**이다.
키가 발급되면 다음을 실행해 실제 응답을 덤프하고 이 두 상수만 수정한다.

    python -m cli probe --date YYYYMMDD
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from rec.models import ApiResponse, MarketArea, RecMarketRow


class MappingError(Exception):
    """응답 구조가 기대와 다를 때 발생한다."""


# --- 여기부터 잠정값. probe 결과로 확정한다. ---------------------------------

FIELD_TRADE_DAY = "tradeDay"
FIELD_AREA = "areaCd"

FIELD_MAP = {
    "trade_count": "tradeCnt",
    "volume": "tradeQty",
    "avg_price": "avgPrice",
    "high_price": "highPrice",
    "low_price": "lowPrice",
    "close_price": "closePrice",
    "trade_amount": "tradeAmt",
}

AREA_MAP = {
    "육지": MarketArea.LAND,
    "제주": MarketArea.JEJU,
    "합계": MarketArea.TOTAL,
}

# --- 잠정값 끝 ---------------------------------------------------------------

DECIMAL_FIELDS = ("volume", "avg_price", "high_price", "low_price", "close_price", "trade_amount")

SUCCESS_RESULT_CODE = "00"


def map_response(response: ApiResponse) -> list[RecMarketRow]:
    """응답 전체를 도메인 행 목록으로 변환한다. 휴장일이면 빈 목록을 반환한다."""
    body = _read_body(response.payload)
    items = _read_items(body)
    return [_map_item(item) for item in items]


def _read_body(payload: dict) -> dict:
    try:
        envelope = payload["response"]
        header = envelope["header"]
        body = envelope.get("body") or {}
    except (KeyError, TypeError) as exc:
        raise MappingError(f"응답 봉투 구조가 예상과 다르다: {_preview(payload)}") from exc

    code = str(header.get("resultCode", "")).strip()
    if code != SUCCESS_RESULT_CODE:
        message = header.get("resultMsg", "")
        raise MappingError(f"API가 오류를 반환했다. resultCode={code} resultMsg={message}")

    return body


def _read_items(body: dict) -> list[dict]:
    """items가 빈 문자열, None, 단일 객체, 목록 중 무엇으로 와도 목록으로 정규화한다."""
    items = body.get("items")
    if not items:
        return []

    if isinstance(items, list):
        raw = items
    elif isinstance(items, dict):
        inner = items.get("item")
        if not inner:
            return []
        raw = inner if isinstance(inner, list) else [inner]
    else:
        return []

    return [item for item in raw if isinstance(item, dict)]


def _map_item(item: dict) -> RecMarketRow:
    trade_date = _parse_trade_date(_require(item, FIELD_TRADE_DAY))
    market_area = _parse_area(_require(item, FIELD_AREA))

    values: dict[str, object] = {}
    for domain_name, api_name in FIELD_MAP.items():
        raw = item.get(api_name)
        if domain_name in DECIMAL_FIELDS:
            values[domain_name] = _parse_decimal(raw)
        else:
            values[domain_name] = _parse_int(raw)

    return RecMarketRow(trade_date=trade_date, market_area=market_area, **values)  # type: ignore[arg-type]


def _require(item: dict, key: str) -> str:
    if key not in item:
        raise MappingError(
            f"필수 필드 '{key}'가 응답에 없다. 실제 키 목록: {sorted(item.keys())}. "
            "mapping.py의 FIELD_MAP을 실제 응답에 맞게 수정하라."
        )
    return str(item[key])


def _parse_trade_date(value: str) -> date:
    text = value.strip().replace("-", "")
    try:
        return datetime.strptime(text, "%Y%m%d").date()
    except ValueError as exc:
        raise MappingError(f"거래일을 해석할 수 없다: {value!r}") from exc


def _parse_area(value: str) -> MarketArea:
    key = value.strip()
    if key not in AREA_MAP:
        raise MappingError(
            f"알 수 없는 시장 구분: {key!r}. mapping.py의 AREA_MAP에 추가하라. "
            f"현재 인식 가능한 값: {sorted(AREA_MAP.keys())}"
        )
    return AREA_MAP[key]


def _parse_decimal(value: object) -> Decimal | None:
    """빈 문자열과 None은 '값 없음'이다. 0으로 대체하지 않는다."""
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if text == "" or text == "-":
        return None
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise MappingError(f"수치를 해석할 수 없다: {value!r}") from exc


def _parse_int(value: object) -> int | None:
    decimal_value = _parse_decimal(value)
    return None if decimal_value is None else int(decimal_value)


def _preview(payload: object, limit: int = 200) -> str:
    return repr(payload)[:limit]
```

- [ ] **Step 8: 테스트 통과 확인**

```powershell
docker compose run --rm collector-test python -m pytest tests/test_mapping.py -v
```

Expected: 8 passed

- [ ] **Step 9: 커밋**

```powershell
cd C:\Dev\RECFlow
git add apps/collector docker-compose.yml
git commit -m "feat(collector): 도메인 모델과 API 매핑 추가

응답 필드명을 아는 파일을 mapping.py 하나로 격리했다. FIELD_MAP과
AREA_MAP은 API 키 미발급 상태의 잠정값이며 probe 명령으로 확정한다.

필드가 사라지면 조용히 None이 되지 않고 실제 키 목록과 함께
MappingError로 실패한다. 빈 문자열은 0이 아니라 '값 없음'으로 다룬다."
```

---

### Task 4: HTTP 클라이언트 — 재시도, 타임아웃, 일일 예산

**Files:**
- Create: `apps/collector/rec/client.py`
- Create: `apps/collector/rec/budget.py`
- Create: `apps/collector/tests/test_client.py`
- Create: `apps/collector/tests/test_budget.py`

**Interfaces:**
- Consumes: `ApiResponse` (Task 3)
- Produces:
  - `DailyBudget(limit: int, today: date | None = None)` — `.consume() -> None`, `.remaining -> int`, raises `BudgetExhausted`
  - `RecApiClient(base_url: str, service_key: str, budget: DailyBudget, timeout_connect: float = 5.0, timeout_read: float = 20.0, max_attempts: int = 3, sleep=time.sleep)` — `.fetch(trade_date: date) -> ApiResponse`
  - `ApiFetchError(Exception)`, `BudgetExhausted(Exception)`

- [ ] **Step 1: 예산 테스트 작성**

`apps/collector/tests/test_budget.py`:

```python
from datetime import date

import pytest

from rec.budget import BudgetExhausted, DailyBudget


def test_consumes_until_limit():
    budget = DailyBudget(limit=3, today=date(2026, 8, 6))
    for _ in range(3):
        budget.consume()
    assert budget.remaining == 0


def test_raises_when_exhausted():
    budget = DailyBudget(limit=1, today=date(2026, 8, 6))
    budget.consume()
    with pytest.raises(BudgetExhausted):
        budget.consume()


def test_resets_on_new_day():
    budget = DailyBudget(limit=1, today=date(2026, 8, 6))
    budget.consume()
    budget.advance_to(date(2026, 8, 7))
    assert budget.remaining == 1
    budget.consume()
```

- [ ] **Step 2: 클라이언트 테스트 작성**

`apps/collector/tests/test_client.py`:

```python
from datetime import date

import httpx
import pytest
import respx

from rec.budget import BudgetExhausted, DailyBudget
from rec.client import ApiFetchError, RecApiClient

BASE_URL = "https://apis.example.test/B552115/RecMarketInfo2"
OK_BODY = {
    "response": {
        "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
        "body": {"items": {"item": []}},
    }
}


def build_client(**overrides) -> RecApiClient:
    kwargs = dict(
        base_url=BASE_URL,
        service_key="test-key",
        budget=DailyBudget(limit=10, today=date(2026, 8, 6)),
        sleep=lambda _seconds: None,
    )
    kwargs.update(overrides)
    return RecApiClient(**kwargs)


@respx.mock
def test_fetch_returns_api_response():
    respx.get(url__startswith=BASE_URL).mock(return_value=httpx.Response(200, json=OK_BODY))
    result = build_client().fetch(date(2026, 8, 6))
    assert result.http_status == 200
    assert result.trade_date == date(2026, 8, 6)
    assert result.payload == OK_BODY


@respx.mock
def test_sends_required_query_parameters():
    route = respx.get(url__startswith=BASE_URL).mock(return_value=httpx.Response(200, json=OK_BODY))
    build_client().fetch(date(2026, 8, 6))
    params = route.calls[0].request.url.params
    assert params["serviceKey"] == "test-key"
    assert params["tradeDay"] == "20260806"
    assert params["dataType"] == "JSON"
    assert params["pageNo"] == "1"
    assert params["numOfRows"] == "100"


@respx.mock
def test_retries_three_times_on_server_error_then_fails():
    route = respx.get(url__startswith=BASE_URL).mock(return_value=httpx.Response(503))
    with pytest.raises(ApiFetchError):
        build_client().fetch(date(2026, 8, 6))
    assert route.call_count == 3


@respx.mock
def test_retries_then_succeeds():
    route = respx.get(url__startswith=BASE_URL)
    route.side_effect = [httpx.Response(503), httpx.Response(200, json=OK_BODY)]
    result = build_client().fetch(date(2026, 8, 6))
    assert result.http_status == 200
    assert route.call_count == 2


@respx.mock
def test_does_not_retry_on_client_error():
    """4xx는 재시도해도 결과가 같으므로 즉시 실패한다."""
    route = respx.get(url__startswith=BASE_URL).mock(return_value=httpx.Response(401))
    with pytest.raises(ApiFetchError):
        build_client().fetch(date(2026, 8, 6))
    assert route.call_count == 1


@respx.mock
def test_backoff_delays_are_exponential():
    delays: list[float] = []
    route = respx.get(url__startswith=BASE_URL).mock(return_value=httpx.Response(503))
    client = build_client(sleep=delays.append)
    with pytest.raises(ApiFetchError):
        client.fetch(date(2026, 8, 6))
    assert delays == [2.0, 8.0]
    assert route.call_count == 3


@respx.mock
def test_budget_is_consumed_once_per_fetch_not_per_attempt():
    """재시도는 같은 논리적 요청이므로 예산은 한 번만 소모한다."""
    respx.get(url__startswith=BASE_URL).mock(return_value=httpx.Response(200, json=OK_BODY))
    budget = DailyBudget(limit=10, today=date(2026, 8, 6))
    client = build_client(budget=budget)
    client.fetch(date(2026, 8, 6))
    assert budget.remaining == 9


@respx.mock
def test_raises_budget_exhausted_without_calling_api():
    route = respx.get(url__startswith=BASE_URL).mock(return_value=httpx.Response(200, json=OK_BODY))
    budget = DailyBudget(limit=0, today=date(2026, 8, 6))
    with pytest.raises(BudgetExhausted):
        build_client(budget=budget).fetch(date(2026, 8, 6))
    assert route.call_count == 0


@respx.mock
def test_retries_on_network_error():
    route = respx.get(url__startswith=BASE_URL)
    route.side_effect = [httpx.ConnectError("boom"), httpx.Response(200, json=OK_BODY)]
    result = build_client().fetch(date(2026, 8, 6))
    assert result.http_status == 200
    assert route.call_count == 2
```

- [ ] **Step 3: 테스트 실패 확인**

```powershell
docker compose run --rm collector-test python -m pytest tests/test_budget.py tests/test_client.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'rec.budget'`

- [ ] **Step 4: `rec/budget.py` 구현**

```python
"""일일 API 호출 예산.

공공데이터포털 개발계정은 하루 100건으로 제한된다. 한도에 부딪혀 수집이
멈추는 대신, 여유를 두고 스스로 멈춘 뒤 중단 지점을 기록한다.
"""

from __future__ import annotations

from datetime import date


class BudgetExhausted(Exception):
    """오늘 사용 가능한 호출 횟수를 모두 썼다."""


class DailyBudget:
    def __init__(self, limit: int, today: date | None = None) -> None:
        if limit < 0:
            raise ValueError("limit은 0 이상이어야 한다")
        self._limit = limit
        self._day = today or date.today()
        self._used = 0

    @property
    def remaining(self) -> int:
        return max(0, self._limit - self._used)

    def advance_to(self, day: date) -> None:
        """날짜가 바뀌면 사용량을 초기화한다."""
        if day != self._day:
            self._day = day
            self._used = 0

    def consume(self, today: date | None = None) -> None:
        if today is not None:
            self.advance_to(today)
        if self.remaining <= 0:
            raise BudgetExhausted(
                f"{self._day} 일일 호출 예산 {self._limit}건을 모두 사용했다. "
                "다음 날 남은 구간부터 이어서 수집한다."
            )
        self._used += 1
```

- [ ] **Step 5: `rec/client.py` 구현**

```python
"""REC 현물시장 Open API HTTP 클라이언트.

HTTP만 안다. 응답 필드의 의미는 mapping.py가, 저장은 repository.py가 맡는다.
"""

from __future__ import annotations

import logging
import time
from datetime import date

import httpx

from rec.budget import DailyBudget
from rec.models import ApiResponse

logger = logging.getLogger(__name__)

RETRY_DELAYS = (2.0, 8.0, 32.0)


class ApiFetchError(Exception):
    """재시도를 모두 소진했거나 재시도해도 소용없는 오류."""


class RecApiClient:
    def __init__(
        self,
        base_url: str,
        service_key: str,
        budget: DailyBudget,
        timeout_connect: float = 5.0,
        timeout_read: float = 20.0,
        max_attempts: int = 3,
        sleep=time.sleep,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._service_key = service_key
        self._budget = budget
        self._timeout = httpx.Timeout(connect=timeout_connect, read=timeout_read, write=timeout_read, pool=timeout_read)
        self._max_attempts = max_attempts
        self._sleep = sleep

    @property
    def source_name(self) -> str:
        return "kpx-openapi"

    def fetch(self, trade_date: date) -> ApiResponse:
        """거래일 하나를 조회한다. 재시도는 같은 논리적 요청이므로 예산은 한 번만 쓴다."""
        self._budget.consume()

        url = f"{self._base_url}/getRecMarketInfo"
        params = {
            "serviceKey": self._service_key,
            "pageNo": "1",
            "numOfRows": "100",
            "dataType": "JSON",
            "tradeDay": trade_date.strftime("%Y%m%d"),
        }

        last_error: Exception | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                with httpx.Client(timeout=self._timeout) as http:
                    response = http.get(url, params=params)

                if 400 <= response.status_code < 500:
                    raise ApiFetchError(
                        f"{trade_date} 요청이 {response.status_code}로 거부되었다. "
                        "인증키와 요청 파라미터를 확인하라. 재시도하지 않는다."
                    )
                response.raise_for_status()
                return ApiResponse(
                    trade_date=trade_date,
                    payload=response.json(),
                    http_status=response.status_code,
                    endpoint=str(response.request.url).split("serviceKey=")[0] + "serviceKey=***",
                )
            except ApiFetchError:
                raise
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                logger.warning("REC API 호출 실패 (%s, 시도 %d/%d): %s", trade_date, attempt, self._max_attempts, exc)
                if attempt < self._max_attempts:
                    self._sleep(RETRY_DELAYS[min(attempt - 1, len(RETRY_DELAYS) - 1)])

        raise ApiFetchError(f"{trade_date} 수집을 {self._max_attempts}회 시도했으나 모두 실패했다: {last_error}")
```

- [ ] **Step 6: 테스트 통과 확인**

```powershell
docker compose run --rm collector-test python -m pytest tests/test_budget.py tests/test_client.py -v
```

Expected: 12 passed

- [ ] **Step 7: 커밋**

```powershell
cd C:\Dev\RECFlow
git add apps/collector
git commit -m "feat(collector): HTTP 클라이언트와 일일 예산 추가

3회 지수 백오프(2s, 8s, 32s), connect 5s / read 20s 타임아웃을 적용했다.
4xx는 재시도해도 결과가 같으므로 즉시 실패한다.

재시도는 같은 논리적 요청이므로 개발계정 예산은 fetch 1회당 한 번만
소모한다. 예산이 없으면 API를 호출하지 않고 BudgetExhausted로 멈춘다."
```

---

### Task 5: fixture 소스 — API 키 없이 파이프라인 돌리기

**Files:**
- Create: `apps/collector/rec/fixture_client.py`
- Create: `apps/collector/rec/trading_days.py`
- Create: `apps/collector/tests/test_trading_days.py`
- Create: `apps/collector/tests/test_fixture_client.py`

**Interfaces:**
- Consumes: `ApiResponse`, `MarketArea` (Task 3), `mapping.FIELD_MAP` / `AREA_MAP` (Task 3)
- Produces:
  - `trading_days(start: date, end: date) -> list[date]` — 화·목만 반환
  - `FixtureClient(fixture_dir: Path)` — `.fetch(trade_date: date) -> ApiResponse`, `.source_name -> "fixture"`
  - `generate_fixtures(fixture_dir: Path, start: date, end: date, seed: int = 20260812) -> int`

- [ ] **Step 1: 거래일 테스트 작성**

`apps/collector/tests/test_trading_days.py`:

```python
from datetime import date

from rec.trading_days import trading_days


def test_returns_only_tuesdays_and_thursdays():
    days = trading_days(date(2026, 8, 3), date(2026, 8, 9))
    assert days == [date(2026, 8, 4), date(2026, 8, 6)]


def test_includes_boundaries():
    days = trading_days(date(2026, 8, 4), date(2026, 8, 6))
    assert days == [date(2026, 8, 4), date(2026, 8, 6)]


def test_empty_when_range_has_no_trading_day():
    assert trading_days(date(2026, 8, 7), date(2026, 8, 9)) == []


def test_returns_empty_when_start_after_end():
    assert trading_days(date(2026, 8, 9), date(2026, 8, 3)) == []


def test_three_years_is_about_310_days():
    days = trading_days(date(2023, 8, 12), date(2026, 8, 12))
    assert 300 <= len(days) <= 320
```

- [ ] **Step 2: fixture 클라이언트 테스트 작성**

`apps/collector/tests/test_fixture_client.py`:

```python
from datetime import date
from decimal import Decimal

import pytest

from rec.fixture_client import FixtureClient, generate_fixtures
from rec.mapping import map_response
from rec.models import MarketArea


@pytest.fixture
def fixture_dir(tmp_path):
    generate_fixtures(tmp_path, date(2026, 7, 1), date(2026, 8, 6))
    return tmp_path


def test_generates_one_file_per_trading_day(tmp_path):
    count = generate_fixtures(tmp_path, date(2026, 8, 3), date(2026, 8, 9))
    assert count == 2
    assert (tmp_path / "20260804.json").exists()
    assert (tmp_path / "20260806.json").exists()


def test_generated_fixture_passes_real_mapping(fixture_dir):
    """fixture는 실제 mapping을 통과해야 한다. 통과하지 못하면 파이프라인 검증 가치가 없다."""
    rows = map_response(FixtureClient(fixture_dir).fetch(date(2026, 8, 6)))
    assert len(rows) == 3
    assert {r.market_area for r in rows} == {MarketArea.LAND, MarketArea.JEJU, MarketArea.TOTAL}


def test_total_row_has_close_price_others_do_not(fixture_dir):
    rows = map_response(FixtureClient(fixture_dir).fetch(date(2026, 8, 6)))
    by_area = {r.market_area: r for r in rows}
    assert by_area[MarketArea.TOTAL].close_price is not None
    assert by_area[MarketArea.LAND].close_price is None
    assert by_area[MarketArea.JEJU].close_price is None


def test_prices_are_in_plausible_range(fixture_dir):
    rows = map_response(FixtureClient(fixture_dir).fetch(date(2026, 8, 6)))
    total = next(r for r in rows if r.market_area is MarketArea.TOTAL)
    assert Decimal("50000") < total.avg_price < Decimal("100000")
    assert total.low_price <= total.avg_price <= total.high_price


def test_generation_is_deterministic(tmp_path):
    """같은 seed면 같은 데이터가 나와야 재현 가능한 테스트가 된다."""
    a, b = tmp_path / "a", tmp_path / "b"
    generate_fixtures(a, date(2026, 8, 3), date(2026, 8, 9), seed=42)
    generate_fixtures(b, date(2026, 8, 3), date(2026, 8, 9), seed=42)
    assert (a / "20260806.json").read_text(encoding="utf-8") == (b / "20260806.json").read_text(encoding="utf-8")


def test_missing_day_returns_empty_items(fixture_dir):
    """fixture가 없는 날은 휴장일처럼 빈 응답을 돌려준다."""
    response = FixtureClient(fixture_dir).fetch(date(2026, 8, 5))
    assert map_response(response) == []


def test_source_name(fixture_dir):
    assert FixtureClient(fixture_dir).source_name == "fixture"
```

- [ ] **Step 3: 테스트 실패 확인**

```powershell
docker compose run --rm collector-test python -m pytest tests/test_trading_days.py tests/test_fixture_client.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'rec.trading_days'`

- [ ] **Step 4: `rec/trading_days.py` 구현**

```python
"""REC 현물시장 거래일.

시장은 매주 화요일과 목요일 10:00~16:00에 운영된다. 공휴일에는 휴장하지만
공휴일 API를 별도로 연동하지 않는다. 화·목을 후보로 삼고, 실제 데이터가
없으면 수집 단계에서 NO_DATA로 표시해 반복 재시도를 멈춘다.
"""

from __future__ import annotations

from datetime import date, timedelta

TUESDAY = 1
THURSDAY = 3
TRADING_WEEKDAYS = frozenset({TUESDAY, THURSDAY})


def trading_days(start: date, end: date) -> list[date]:
    """start와 end를 포함한 구간의 거래일 후보를 오름차순으로 반환한다."""
    if start > end:
        return []
    days: list[date] = []
    current = start
    while current <= end:
        if current.weekday() in TRADING_WEEKDAYS:
            days.append(current)
        current += timedelta(days=1)
    return days
```

- [ ] **Step 5: `rec/fixture_client.py` 구현**

```python
"""fixture 소스.

RecApiClient와 같은 인터페이스를 제공하되 HTTP 대신 파일을 읽는다.
client 계층만 교체되므로 mapping / validation / repository는 실제와
완전히 동일한 경로를 지난다.

생성되는 JSON은 mapping.py의 FIELD_MAP과 AREA_MAP을 참조해 만들어진다.
필드명을 여기에 중복해서 쓰지 않기 위함이다.
"""

from __future__ import annotations

import json
import random
from datetime import date
from decimal import Decimal
from pathlib import Path

from rec.mapping import AREA_MAP, FIELD_MAP, FIELD_AREA, FIELD_TRADE_DAY
from rec.models import ApiResponse, MarketArea
from rec.trading_days import trading_days

EMPTY_PAYLOAD = {
    "response": {
        "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
        "body": {"numOfRows": 100, "pageNo": 1, "totalCount": 0, "items": ""},
    }
}

BASE_PRICE = Decimal("68000")
MIN_PRICE = Decimal("55000")
MAX_PRICE = Decimal("88000")


class FixtureClient:
    def __init__(self, fixture_dir: Path) -> None:
        self._dir = Path(fixture_dir)

    @property
    def source_name(self) -> str:
        return "fixture"

    def fetch(self, trade_date: date) -> ApiResponse:
        path = self._dir / f"{trade_date:%Y%m%d}.json"
        payload = json.loads(path.read_text(encoding="utf-8")) if path.exists() else EMPTY_PAYLOAD
        return ApiResponse(
            trade_date=trade_date,
            payload=payload,
            http_status=200,
            endpoint=f"fixture://{path.name}",
        )


def generate_fixtures(fixture_dir: Path, start: date, end: date, seed: int = 20260812) -> int:
    """구간의 모든 거래일에 대해 그럴듯한 응답 파일을 만든다. 같은 seed면 같은 결과가 나온다."""
    fixture_dir = Path(fixture_dir)
    fixture_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(seed)
    price = BASE_PRICE
    written = 0

    for day in trading_days(start, end):
        # 완만한 추세 + 잡음. 실제 REC 가격의 움직임을 흉내낸다.
        drift = Decimal(str(round(rng.gauss(15, 700), 2)))
        price = _clamp(price + drift, MIN_PRICE, MAX_PRICE)

        land = _area_values(rng, price, volume_base=180000)
        jeju = _area_values(rng, price - Decimal("600"), volume_base=9000)
        total_volume = land["volume"] + jeju["volume"]
        total_avg = _round2((land["avg"] * land["volume"] + jeju["avg"] * jeju["volume"]) / total_volume)

        items = [
            _item(day, MarketArea.LAND, land, close_price=None, trade_amount=None),
            _item(day, MarketArea.JEJU, jeju, close_price=None, trade_amount=None),
            _item(
                day,
                MarketArea.TOTAL,
                {
                    "count": land["count"] + jeju["count"],
                    "volume": total_volume,
                    "avg": total_avg,
                    "high": max(land["high"], jeju["high"]),
                    "low": min(land["low"], jeju["low"]),
                },
                close_price=_round2(total_avg + Decimal(str(round(rng.uniform(-250, 250), 2)))),
                trade_amount=_round2(total_avg * total_volume),
            ),
        ]

        payload = {
            "response": {
                "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
                "body": {"numOfRows": 100, "pageNo": 1, "totalCount": len(items), "items": {"item": items}},
            }
        }
        target = fixture_dir / f"{day:%Y%m%d}.json"
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        written += 1

    return written


def _area_values(rng: random.Random, center: Decimal, volume_base: int) -> dict:
    avg = _round2(center)
    spread = Decimal(str(round(rng.uniform(300, 1500), 2)))
    return {
        "count": rng.randint(int(volume_base / 500), int(volume_base / 300)),
        "volume": Decimal(rng.randint(int(volume_base * 0.6), int(volume_base * 1.4))),
        "avg": avg,
        "high": _round2(avg + spread),
        "low": _round2(avg - spread),
    }


def _item(day: date, area: MarketArea, values: dict, close_price: Decimal | None, trade_amount: Decimal | None) -> dict:
    area_label = next(label for label, mapped in AREA_MAP.items() if mapped is area)
    return {
        FIELD_TRADE_DAY: f"{day:%Y%m%d}",
        FIELD_AREA: area_label,
        FIELD_MAP["trade_count"]: str(values["count"]),
        FIELD_MAP["volume"]: str(values["volume"]),
        FIELD_MAP["avg_price"]: str(values["avg"]),
        FIELD_MAP["high_price"]: str(values["high"]),
        FIELD_MAP["low_price"]: str(values["low"]),
        FIELD_MAP["close_price"]: "" if close_price is None else str(close_price),
        FIELD_MAP["trade_amount"]: "" if trade_amount is None else str(trade_amount),
    }


def _clamp(value: Decimal, low: Decimal, high: Decimal) -> Decimal:
    return max(low, min(high, value))


def _round2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))
```

- [ ] **Step 6: 테스트 통과 확인**

```powershell
docker compose run --rm collector-test python -m pytest tests/test_trading_days.py tests/test_fixture_client.py -v
```

Expected: 12 passed

- [ ] **Step 7: 커밋**

```powershell
cd C:\Dev\RECFlow
git add apps/collector
git commit -m "feat(collector): fixture 소스와 거래일 계산 추가

client 계층만 교체하고 mapping·검증·적재는 실제 경로를 그대로 지나도록
FixtureClient가 RecApiClient와 같은 인터페이스를 제공한다.

fixture 생성기는 mapping.py의 FIELD_MAP을 참조해 JSON을 만든다.
필드명을 두 곳에 두지 않기 위함이며, 생성 결과가 실제 mapping을
통과하는지 테스트로 확인한다."
```

---

### Task 6: 검증 규칙

**Files:**
- Create: `apps/collector/rec/validation.py`
- Create: `apps/collector/tests/test_validation.py`

**Interfaces:**
- Consumes: `RecMarketRow` (Task 3)
- Produces: `validate_rows(rows: list[RecMarketRow]) -> list[str]` — 위반 사유 목록. 비어 있으면 정상.

- [ ] **Step 1: 테스트 작성**

`apps/collector/tests/test_validation.py`:

```python
from datetime import date
from decimal import Decimal

from rec.models import MarketArea, RecMarketRow
from rec.validation import validate_rows


def row(**overrides) -> RecMarketRow:
    base = dict(
        trade_date=date(2026, 8, 6),
        market_area=MarketArea.TOTAL,
        trade_count=450,
        volume=Decimal("194500"),
        avg_price=Decimal("71450"),
        high_price=Decimal("72300"),
        low_price=Decimal("70200"),
        close_price=Decimal("71600"),
        trade_amount=Decimal("13897550000"),
    )
    base.update(overrides)
    return RecMarketRow(**base)


def test_valid_row_has_no_issues():
    assert validate_rows([row()]) == []


def test_avg_price_above_high_price_is_reported():
    issues = validate_rows([row(avg_price=Decimal("99999"))])
    assert len(issues) == 1
    assert "평균가" in issues[0]


def test_close_price_below_low_price_is_reported():
    issues = validate_rows([row(close_price=Decimal("100"))])
    assert len(issues) == 1
    assert "종가" in issues[0]


def test_negative_volume_is_reported():
    issues = validate_rows([row(volume=Decimal("-1"))])
    assert len(issues) == 1
    assert "거래량" in issues[0]


def test_zero_price_is_reported():
    issues = validate_rows([row(avg_price=Decimal("0"))])
    assert any("0 이하" in issue for issue in issues)


def test_none_values_are_not_violations():
    """육지 행의 종가 None은 정상이다. 값 없음과 잘못된 값을 구분한다."""
    assert validate_rows([row(market_area=MarketArea.LAND, close_price=None, trade_amount=None)]) == []


def test_high_below_low_is_reported():
    issues = validate_rows([row(high_price=Decimal("60000"), low_price=Decimal("70000"))])
    assert any("최고가" in issue for issue in issues)


def test_reports_every_violating_row():
    issues = validate_rows([row(volume=Decimal("-1")), row(market_area=MarketArea.LAND, avg_price=Decimal("-5"))])
    assert len(issues) == 2
```

- [ ] **Step 2: 테스트 실패 확인**

```powershell
docker compose run --rm collector-test python -m pytest tests/test_validation.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'rec.validation'`

- [ ] **Step 3: `rec/validation.py` 구현**

```python
"""수집 값 검증.

위반이 있어도 저장은 한다. 원본을 버리지 않고 PARTIAL로 표시해 관리자가
판단하게 하는 편이, 조용히 버려서 데이터가 비는 것보다 낫다.
"""

from __future__ import annotations

from decimal import Decimal

from rec.models import RecMarketRow

ZERO = Decimal("0")


def validate_rows(rows: list[RecMarketRow]) -> list[str]:
    """위반 사유를 사람이 읽을 수 있는 문장 목록으로 반환한다. 정상이면 빈 목록."""
    issues: list[str] = []
    for row in rows:
        issues.extend(_validate_row(row))
    return issues


def _validate_row(row: RecMarketRow) -> list[str]:
    label = f"{row.trade_date} {row.market_area}"
    issues: list[str] = []

    for name, value in (
        ("평균가", row.avg_price),
        ("종가", row.close_price),
        ("최고가", row.high_price),
        ("최저가", row.low_price),
    ):
        if value is not None and value <= ZERO:
            issues.append(f"{label}: {name}가 0 이하다 ({value})")

    for name, value in (("거래량", row.volume), ("거래금액", row.trade_amount)):
        if value is not None and value < ZERO:
            issues.append(f"{label}: {name}이 음수다 ({value})")

    if row.high_price is not None and row.low_price is not None and row.high_price < row.low_price:
        issues.append(f"{label}: 최고가({row.high_price})가 최저가({row.low_price})보다 낮다")

    issues.extend(_check_within_band("평균가", row.avg_price, row, label))
    issues.extend(_check_within_band("종가", row.close_price, row, label))

    return issues


def _check_within_band(name: str, value: Decimal | None, row: RecMarketRow, label: str) -> list[str]:
    if value is None or row.high_price is None or row.low_price is None:
        return []
    if value > row.high_price:
        return [f"{label}: {name}({value})가 최고가({row.high_price})보다 높다"]
    if value < row.low_price:
        return [f"{label}: {name}({value})가 최저가({row.low_price})보다 낮다"]
    return []
```

- [ ] **Step 4: 테스트 통과 확인**

```powershell
docker compose run --rm collector-test python -m pytest tests/test_validation.py -v
```

Expected: 8 passed

- [ ] **Step 5: 커밋**

```powershell
cd C:\Dev\RECFlow
git add apps/collector
git commit -m "feat(collector): 수집 값 검증 규칙 추가

가격이 최저~최고 범위를 벗어나거나 0 이하, 거래량이 음수인 경우를
잡아낸다. 위반해도 저장은 하고 PARTIAL로 표시한다. 조용히 버려서
데이터가 비는 것보다 관리자가 판단하게 하는 편이 낫다.

None은 위반이 아니다. 육지 행의 종가 None은 정상이므로
'값 없음'과 '잘못된 값'을 구분한다."
```

---

### Task 7: 리포지토리 — UPSERT와 실행 이력

**Files:**
- Create: `apps/collector/rec/repository.py`
- Create: `apps/collector/tests/conftest.py`
- Create: `apps/collector/tests/test_repository.py`

**Interfaces:**
- Consumes: `RecMarketRow`, `ApiResponse` (Task 3), 테이블 스키마 (Task 2)
- Produces:
  - `RecRepository(dsn: str)` with:
    - `.start_run(job_type: str, target_date: date | None) -> int`
    - `.finish_run(run_id: int, status: str, attempts: int, rows_upserted: int, error_message: str | None = None) -> None`
    - `.save_raw(run_id: int, response: ApiResponse) -> int`
    - `.upsert_rows(rows: list[RecMarketRow], source: str) -> int`
    - `.existing_trade_dates(start: date, end: date) -> set[date]`
    - `.settled_trade_dates(start: date, end: date) -> set[date]`
    - `.last_successful_run() -> dict | None`
    - 테스트 지원: `.count_market_rows() -> int`, `.count_raw_rows() -> int`, `.fetch_avg_price(trade_date, area) -> Decimal | None`, `.fetch_updated_at(trade_date, area) -> datetime | None`, `.truncate_market_tables() -> None`

- [ ] **Step 1: 테스트 공용 설정 작성**

`apps/collector/tests/conftest.py`:

```python
import os
from datetime import date
from decimal import Decimal

import pytest

from rec.models import ApiResponse, MarketArea, RecMarketRow
from rec.repository import RecRepository

TEST_DSN = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")


@pytest.fixture
def repo():
    """실제 PostgreSQL에 붙는다. UPSERT는 진짜 DB가 아니면 검증되지 않는다."""
    if not TEST_DSN:
        pytest.skip("DATABASE_URL 또는 TEST_DATABASE_URL이 설정되지 않았다")
    repository = RecRepository(TEST_DSN)
    repository.truncate_market_tables()
    yield repository
    repository.truncate_market_tables()


def make_row(trade_date=date(2026, 8, 6), area=MarketArea.TOTAL, avg_price="71450") -> RecMarketRow:
    return RecMarketRow(
        trade_date=trade_date,
        market_area=area,
        trade_count=450,
        volume=Decimal("194500"),
        avg_price=Decimal(avg_price),
        high_price=Decimal("99000"),
        low_price=Decimal("10000"),
        close_price=Decimal("71600") if area is MarketArea.TOTAL else None,
        trade_amount=Decimal("13897550000") if area is MarketArea.TOTAL else None,
    )


def make_response(trade_date=date(2026, 8, 6)) -> ApiResponse:
    return ApiResponse(
        trade_date=trade_date,
        payload={"response": {"header": {"resultCode": "00"}, "body": {"items": {"item": []}}}},
        http_status=200,
        endpoint="fixture://test",
    )
```

- [ ] **Step 2: 리포지토리 테스트 작성**

`apps/collector/tests/test_repository.py`:

```python
from datetime import date
from decimal import Decimal

from rec.models import MarketArea
from tests.conftest import make_response, make_row


def test_upsert_inserts_new_rows(repo):
    inserted = repo.upsert_rows([make_row(area=MarketArea.LAND), make_row(area=MarketArea.TOTAL)], source="fixture")
    assert inserted == 2
    assert repo.count_market_rows() == 2


def test_upsert_twice_does_not_duplicate(repo):
    """같은 거래일을 두 번 수집해도 행이 늘지 않아야 한다. 이 계획의 핵심 보장이다."""
    repo.upsert_rows([make_row()], source="fixture")
    repo.upsert_rows([make_row()], source="fixture")
    assert repo.count_market_rows() == 1


def test_upsert_updates_changed_values(repo):
    repo.upsert_rows([make_row(avg_price="71450")], source="fixture")
    repo.upsert_rows([make_row(avg_price="72000")], source="fixture")
    assert repo.fetch_avg_price(date(2026, 8, 6), MarketArea.TOTAL) == Decimal("72000.00")


def test_upsert_bumps_updated_at(repo):
    repo.upsert_rows([make_row(avg_price="71450")], source="fixture")
    first = repo.fetch_updated_at(date(2026, 8, 6), MarketArea.TOTAL)
    repo.upsert_rows([make_row(avg_price="72000")], source="fixture")
    assert repo.fetch_updated_at(date(2026, 8, 6), MarketArea.TOTAL) > first


def test_land_and_total_coexist_for_same_date(repo):
    repo.upsert_rows(
        [make_row(area=MarketArea.LAND), make_row(area=MarketArea.JEJU), make_row(area=MarketArea.TOTAL)],
        source="fixture",
    )
    assert repo.count_market_rows() == 3


def test_run_lifecycle(repo):
    run_id = repo.start_run("BACKFILL", date(2026, 8, 6))
    repo.finish_run(run_id, status="SUCCESS", attempts=1, rows_upserted=3)
    last = repo.last_successful_run()
    assert last is not None
    assert last["target_date"] == date(2026, 8, 6)
    assert last["rows_upserted"] == 3


def test_failed_run_is_not_reported_as_last_successful(repo):
    run_id = repo.start_run("SCHEDULED", date(2026, 8, 6))
    repo.finish_run(run_id, status="FAILED", attempts=3, rows_upserted=0, error_message="timeout")
    assert repo.last_successful_run() is None


def test_save_raw_links_to_run(repo):
    run_id = repo.start_run("MANUAL", date(2026, 8, 6))
    raw_id = repo.save_raw(run_id, make_response())
    assert raw_id > 0
    assert repo.count_raw_rows() == 1


def test_raw_is_saved_even_without_market_rows(repo):
    """매핑이 실패해도 원본은 남아야 재처리로 복구할 수 있다."""
    run_id = repo.start_run("MANUAL", date(2026, 8, 6))
    repo.save_raw(run_id, make_response())
    assert repo.count_raw_rows() == 1
    assert repo.count_market_rows() == 0


def test_existing_trade_dates(repo):
    repo.upsert_rows([make_row(trade_date=date(2026, 8, 4)), make_row(trade_date=date(2026, 8, 6))], source="fixture")
    found = repo.existing_trade_dates(date(2026, 8, 1), date(2026, 8, 31))
    assert found == {date(2026, 8, 4), date(2026, 8, 6)}


def test_settled_trade_dates_includes_no_data_days(repo):
    """NO_DATA로 확정된 휴장일은 누락일 재시도 대상에서 빠져야 한다."""
    repo.upsert_rows([make_row(trade_date=date(2026, 8, 4))], source="fixture")
    run_id = repo.start_run("GAP_SCAN", date(2026, 8, 6))
    repo.finish_run(run_id, status="NO_DATA", attempts=3, rows_upserted=0)
    settled = repo.settled_trade_dates(date(2026, 8, 1), date(2026, 8, 31))
    assert settled == {date(2026, 8, 4), date(2026, 8, 6)}
```

- [ ] **Step 3: 테스트 실패 확인**

```powershell
cd C:\Dev\RECFlow
docker compose run --rm collector-test python -m pytest tests/test_repository.py -v
```

`collector-test` 서비스가 `DATABASE_URL`을 `db:5432`로 주입하므로 별도 환경변수 설정이 필요 없다.

Expected: FAIL — `ModuleNotFoundError: No module named 'rec.repository'`

- [ ] **Step 4: `rec/repository.py` 구현**

```python
"""DB 접근.

SQL만 안다. HTTP와 응답 필드명을 알지 못한다.

이 파일은 어떤 DDL도 실행하지 않는다. 테이블 생성과 변경은 Prisma
마이그레이션이 단독으로 담당한다. 스키마 정의가 두 곳에 있으면 반드시 어긋난다.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from rec.models import ApiResponse, MarketArea, RecMarketRow

UPSERT_SQL = """
INSERT INTO rec_market (
    trade_date, market_area, trade_count, volume,
    avg_price, high_price, low_price, close_price, trade_amount,
    source, created_at, updated_at
) VALUES (
    %(trade_date)s, %(market_area)s, %(trade_count)s, %(volume)s,
    %(avg_price)s, %(high_price)s, %(low_price)s, %(close_price)s, %(trade_amount)s,
    %(source)s, NOW(), NOW()
)
ON CONFLICT (trade_date, market_area) DO UPDATE SET
    trade_count  = EXCLUDED.trade_count,
    volume       = EXCLUDED.volume,
    avg_price    = EXCLUDED.avg_price,
    high_price   = EXCLUDED.high_price,
    low_price    = EXCLUDED.low_price,
    close_price  = EXCLUDED.close_price,
    trade_amount = EXCLUDED.trade_amount,
    source       = EXCLUDED.source,
    updated_at   = NOW()
"""


class RecRepository:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self._dsn, row_factory=dict_row)

    # --- 실행 이력 --------------------------------------------------------

    def start_run(self, job_type: str, target_date: date | None) -> int:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO collection_runs (job_type, target_date, status, attempts, rows_upserted, started_at)
                VALUES (%s::"CollectionJobType", %s, 'FAILED'::"CollectionStatus", 0, 0, NOW())
                RETURNING id
                """,
                (job_type, target_date),
            )
            return cur.fetchone()["id"]

    def finish_run(
        self,
        run_id: int,
        status: str,
        attempts: int,
        rows_upserted: int,
        error_message: str | None = None,
    ) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE collection_runs
                   SET status = %s::"CollectionStatus",
                       attempts = %s,
                       rows_upserted = %s,
                       error_message = %s,
                       finished_at = NOW()
                 WHERE id = %s
                """,
                (status, attempts, rows_upserted, error_message, run_id),
            )

    def last_successful_run(self) -> dict | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, job_type, target_date, rows_upserted, started_at, finished_at
                  FROM collection_runs
                 WHERE status = 'SUCCESS'
                 ORDER BY finished_at DESC NULLS LAST
                 LIMIT 1
                """
            )
            return cur.fetchone()

    # --- 원본 보존 --------------------------------------------------------

    def save_raw(self, run_id: int, response: ApiResponse) -> int:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO rec_market_raw (trade_date, endpoint, http_status, payload, fetched_at, collection_run_id)
                VALUES (%s, %s, %s, %s, NOW(), %s)
                RETURNING id
                """,
                (
                    response.trade_date,
                    response.endpoint,
                    response.http_status,
                    Jsonb(response.payload),
                    run_id,
                ),
            )
            return cur.fetchone()["id"]

    # --- 시세 적재 --------------------------------------------------------

    def upsert_rows(self, rows: list[RecMarketRow], source: str) -> int:
        if not rows:
            return 0
        params = [
            {
                "trade_date": row.trade_date,
                "market_area": row.market_area.value,
                "trade_count": row.trade_count,
                "volume": row.volume,
                "avg_price": row.avg_price,
                "high_price": row.high_price,
                "low_price": row.low_price,
                "close_price": row.close_price,
                "trade_amount": row.trade_amount,
                "source": source,
            }
            for row in rows
        ]
        with self._connect() as conn, conn.cursor() as cur:
            cur.executemany(UPSERT_SQL, params)
        return len(params)

    # --- 조회 -------------------------------------------------------------

    def existing_trade_dates(self, start: date, end: date) -> set[date]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT trade_date FROM rec_market WHERE trade_date BETWEEN %s AND %s",
                (start, end),
            )
            return {row["trade_date"] for row in cur.fetchall()}

    def settled_trade_dates(self, start: date, end: date) -> set[date]:
        """데이터가 있거나 휴장일로 확정된 날. 누락일 재시도 대상에서 제외한다."""
        no_data: set[date]
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT target_date
                  FROM collection_runs
                 WHERE status = 'NO_DATA' AND target_date BETWEEN %s AND %s
                """,
                (start, end),
            )
            no_data = {row["target_date"] for row in cur.fetchall() if row["target_date"]}
        return self.existing_trade_dates(start, end) | no_data

    # --- 테스트 지원 ------------------------------------------------------

    def count_market_rows(self) -> int:
        return self._scalar("SELECT COUNT(*) AS n FROM rec_market")

    def count_raw_rows(self) -> int:
        return self._scalar("SELECT COUNT(*) AS n FROM rec_market_raw")

    def fetch_avg_price(self, trade_date: date, area: MarketArea) -> Decimal | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT avg_price FROM rec_market WHERE trade_date = %s AND market_area = %s::\"MarketArea\"",
                (trade_date, area.value),
            )
            found = cur.fetchone()
            return found["avg_price"] if found else None

    def fetch_updated_at(self, trade_date: date, area: MarketArea) -> datetime | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT updated_at FROM rec_market WHERE trade_date = %s AND market_area = %s::\"MarketArea\"",
                (trade_date, area.value),
            )
            found = cur.fetchone()
            return found["updated_at"] if found else None

    def truncate_market_tables(self) -> None:
        """테스트 격리용. 시장 데이터만 비우고 회사 데이터는 건드리지 않는다."""
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("TRUNCATE rec_market_raw, rec_market, collection_runs RESTART IDENTITY CASCADE")

    def _scalar(self, sql: str) -> int:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql)
            return int(cur.fetchone()["n"])
```

- [ ] **Step 5: 테스트 통과 확인**

```powershell
docker compose run --rm collector-test python -m pytest tests/test_repository.py -v
```

Expected: 11 passed. `test_upsert_twice_does_not_duplicate`가 실패하면 Task 2의 UNIQUE 제약을 다시 확인한다.

- [ ] **Step 6: 전체 테스트 통과 확인**

```powershell
docker compose run --rm collector-test
```

Expected: 모두 통과 (39 passed 내외)

- [ ] **Step 7: 커밋**

```powershell
cd C:\Dev\RECFlow
git add apps/collector
git commit -m "feat(collector): 리포지토리 추가 — UPSERT, 원본 보존, 실행 이력

같은 거래일을 여러 번 수집해도 (trade_date, market_area) 유니크 제약에
따라 행이 늘지 않고 갱신된다. 실제 PostgreSQL에 대해 검증했다.

DDL은 실행하지 않는다. 스키마는 Prisma가 단독으로 소유한다.
NO_DATA로 확정된 휴장일은 settled_trade_dates에 포함되어
누락일 재시도 대상에서 빠진다."
```

---

### Task 8: 서비스 조립과 CLI

**Files:**
- Create: `apps/collector/rec/service.py`
- Create: `apps/collector/config.py`
- Create: `apps/collector/cli.py`
- Create: `apps/collector/tests/test_service.py`

**Interfaces:**
- Consumes: Task 3~7 전체
- Produces:
  - `CollectionOutcome` (frozen dataclass): `run_id: int`, `trade_date: date`, `status: str`, `rows_upserted: int`, `issues: list[str]`
  - `CollectorService(repository: RecRepository, source)` — `source`는 `.fetch(date) -> ApiResponse`와 `.source_name -> str`을 가진 객체다 (`RecApiClient` 또는 `FixtureClient`). 메서드: `.collect_day(trade_date, job_type="MANUAL") -> CollectionOutcome`, `.backfill(start, end, job_type="BACKFILL") -> list[CollectionOutcome]`, `.scan_gaps(days=30, today=None) -> list[CollectionOutcome]`
  - `load_config() -> Config` — `.database_url`, `.kpx_api_key`, `.kpx_base_url`, `.kpx_daily_budget`, `.fixture_dir`, `.collector_port`

- [ ] **Step 1: 서비스 테스트 작성**

`apps/collector/tests/test_service.py`:

```python
from datetime import date

import pytest

from rec.fixture_client import generate_fixtures, FixtureClient
from rec.service import CollectorService
from tests.conftest import make_response


@pytest.fixture
def fixture_source(tmp_path):
    generate_fixtures(tmp_path, date(2026, 7, 1), date(2026, 8, 6))
    return FixtureClient(tmp_path)


def test_collect_day_stores_rows_and_raw(repo, fixture_source):
    outcome = CollectorService(repo, fixture_source).collect_day(date(2026, 8, 6))
    assert outcome.status == "SUCCESS"
    assert outcome.rows_upserted == 3
    assert repo.count_market_rows() == 3
    assert repo.count_raw_rows() == 1


def test_collect_day_is_idempotent(repo, fixture_source):
    service = CollectorService(repo, fixture_source)
    service.collect_day(date(2026, 8, 6))
    service.collect_day(date(2026, 8, 6))
    assert repo.count_market_rows() == 3
    assert repo.count_raw_rows() == 2  # 원본은 호출마다 남는다


def test_collect_day_on_holiday_returns_no_data(repo, fixture_source):
    """fixture가 없는 날은 휴장일로 간주하고 NO_DATA로 확정한다."""
    outcome = CollectorService(repo, fixture_source).collect_day(date(2026, 8, 5))
    assert outcome.status == "NO_DATA"
    assert outcome.rows_upserted == 0
    assert repo.count_market_rows() == 0


def test_backfill_collects_every_trading_day(repo, fixture_source):
    outcomes = CollectorService(repo, fixture_source).backfill(date(2026, 8, 1), date(2026, 8, 8))
    assert len(outcomes) == 2  # 8/4 화, 8/6 목
    assert repo.count_market_rows() == 6


def test_backfill_skips_already_collected_days(repo, fixture_source):
    service = CollectorService(repo, fixture_source)
    service.collect_day(date(2026, 8, 4))
    outcomes = service.backfill(date(2026, 8, 1), date(2026, 8, 8))
    assert len(outcomes) == 1


def test_backfill_skips_no_data_days_on_second_run(repo, fixture_source):
    """NO_DATA로 확정된 휴장일은 다시 시도하지 않는다."""
    service = CollectorService(repo, fixture_source)
    service.backfill(date(2026, 7, 1), date(2026, 8, 6))
    assert service.backfill(date(2026, 7, 1), date(2026, 8, 6)) == []


def test_run_is_recorded_for_every_collection(repo, fixture_source):
    CollectorService(repo, fixture_source).collect_day(date(2026, 8, 6))
    last = repo.last_successful_run()
    assert last is not None
    assert last["target_date"] == date(2026, 8, 6)


def test_mapping_failure_still_saves_raw_and_records_failed(repo):
    class BrokenSource:
        source_name = "broken"

        def fetch(self, trade_date):
            response = make_response(trade_date)
            response.payload["response"]["body"]["items"] = {"item": [{"unexpectedKey": "x"}]}
            return response

    outcome = CollectorService(repo, BrokenSource()).collect_day(date(2026, 8, 6))
    assert outcome.status == "FAILED"
    assert repo.count_raw_rows() == 1
    assert repo.count_market_rows() == 0


def test_validation_issue_marks_partial(repo):
    class SuspiciousSource:
        source_name = "suspicious"

        def fetch(self, trade_date):
            response = make_response(trade_date)
            response.payload["response"]["body"]["items"] = {
                "item": [
                    {
                        "tradeDay": "20260806",
                        "areaCd": "합계",
                        "tradeCnt": "10",
                        "tradeQty": "-500",
                        "avgPrice": "71000",
                        "highPrice": "72000",
                        "lowPrice": "70000",
                        "closePrice": "71500",
                        "tradeAmt": "1000",
                    }
                ]
            }
            return response

    outcome = CollectorService(repo, SuspiciousSource()).collect_day(date(2026, 8, 6))
    assert outcome.status == "PARTIAL"
    assert repo.count_market_rows() == 1  # 의심스러워도 저장은 한다
    assert any("거래량" in issue for issue in outcome.issues)
```

- [ ] **Step 2: 테스트 실패 확인**

```powershell
docker compose run --rm collector-test python -m pytest tests/test_service.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'rec.service'`

- [ ] **Step 3: `rec/service.py` 구현**

```python
"""수집 흐름 조립.

client → mapping → validation → repository 순서와 실패 시 무엇을 남길지만
결정한다. 각 모듈의 내부는 알지 못한다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta

from rec.budget import BudgetExhausted
from rec.mapping import MappingError, map_response
from rec.repository import RecRepository
from rec.trading_days import trading_days
from rec.validation import validate_rows

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CollectionOutcome:
    run_id: int
    trade_date: date
    status: str
    rows_upserted: int
    issues: list[str] = field(default_factory=list)


class CollectorService:
    def __init__(self, repository: RecRepository, source) -> None:
        self._repo = repository
        self._source = source

    def collect_day(self, trade_date: date, job_type: str = "MANUAL") -> CollectionOutcome:
        run_id = self._repo.start_run(job_type, trade_date)

        try:
            response = self._source.fetch(trade_date)
        except BudgetExhausted as exc:
            self._repo.finish_run(run_id, "FAILED", attempts=0, rows_upserted=0, error_message=str(exc))
            raise
        except Exception as exc:  # noqa: BLE001 - 어떤 실패든 이력에 남긴다
            self._repo.finish_run(run_id, "FAILED", attempts=3, rows_upserted=0, error_message=str(exc))
            logger.error("%s 수집 실패: %s", trade_date, exc)
            return CollectionOutcome(run_id, trade_date, "FAILED", 0, [str(exc)])

        # 원본은 매핑보다 먼저 저장한다. 매핑이 실패해도 재처리로 복구할 수 있어야 한다.
        self._repo.save_raw(run_id, response)

        try:
            rows = map_response(response)
        except MappingError as exc:
            self._repo.finish_run(run_id, "FAILED", attempts=1, rows_upserted=0, error_message=str(exc))
            logger.error("%s 매핑 실패: %s", trade_date, exc)
            return CollectionOutcome(run_id, trade_date, "FAILED", 0, [str(exc)])

        if not rows:
            self._repo.finish_run(run_id, "NO_DATA", attempts=1, rows_upserted=0)
            logger.info("%s 데이터 없음 (휴장일로 확정)", trade_date)
            return CollectionOutcome(run_id, trade_date, "NO_DATA", 0, [])

        issues = validate_rows(rows)
        upserted = self._repo.upsert_rows(rows, source=self._source.source_name)
        status = "PARTIAL" if issues else "SUCCESS"
        self._repo.finish_run(
            run_id,
            status,
            attempts=1,
            rows_upserted=upserted,
            error_message="; ".join(issues) if issues else None,
        )
        if issues:
            logger.warning("%s 검증 경고 %d건: %s", trade_date, len(issues), issues)
        return CollectionOutcome(run_id, trade_date, status, upserted, issues)

    def backfill(self, start: date, end: date, job_type: str = "BACKFILL") -> list[CollectionOutcome]:
        """이미 확정된 날은 건너뛴다. 예산이 소진되면 중단하고 지금까지의 결과를 돌려준다."""
        settled = self._repo.settled_trade_dates(start, end)
        outcomes: list[CollectionOutcome] = []

        for day in trading_days(start, end):
            if day in settled:
                continue
            try:
                outcomes.append(self.collect_day(day, job_type=job_type))
            except BudgetExhausted as exc:
                logger.warning("예산 소진으로 %s에서 중단한다: %s", day, exc)
                break

        return outcomes

    def scan_gaps(self, days: int = 30, today: date | None = None) -> list[CollectionOutcome]:
        end = today or date.today()
        return self.backfill(end - timedelta(days=days), end, job_type="GAP_SCAN")
```

- [ ] **Step 4: `config.py` 구현**

```python
"""환경변수 로딩. 기본값은 로컬 개발 기준이다."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_FIXTURE_DIR = Path(__file__).parent / "fixtures"


@dataclass(frozen=True, slots=True)
class Config:
    database_url: str
    kpx_api_key: str
    kpx_base_url: str
    kpx_daily_budget: int
    fixture_dir: Path
    collector_port: int


def load_config() -> Config:
    # 컨테이너에서는 compose가 환경변수를 직접 주입하므로 .env가 없다.
    # 호스트에서 직접 실행하는 경우에만 상위 디렉토리의 .env를 찾아 읽는다.
    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".env"
        if candidate.exists():
            load_dotenv(candidate)
            break

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("DATABASE_URL이 설정되지 않았다. .env를 확인하라.")

    return Config(
        database_url=database_url,
        kpx_api_key=os.environ.get("KPX_API_KEY", ""),
        kpx_base_url=os.environ.get("KPX_BASE_URL", "https://apis.data.go.kr/B552115/RecMarketInfo2"),
        kpx_daily_budget=int(os.environ.get("KPX_DAILY_BUDGET", "80")),
        fixture_dir=Path(os.environ.get("FIXTURE_DIR", DEFAULT_FIXTURE_DIR)),
        collector_port=int(os.environ.get("COLLECTOR_PORT", "8000")),
    )
```

- [ ] **Step 5: `cli.py` 구현**

```python
"""수집기 명령줄 인터페이스.

    python -m cli gen-fixture --years 3
    python -m cli collect --date 20260806 --source fixture
    python -m cli backfill --from 20230812 --to 20260812 --source fixture
    python -m cli probe --date 20260806
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from config import load_config
from rec.budget import DailyBudget
from rec.client import RecApiClient
from rec.fixture_client import FixtureClient, generate_fixtures
from rec.repository import RecRepository
from rec.service import CollectorService

SAMPLE_DIR = Path(__file__).resolve().parents[2] / "docs" / "api-samples"


def parse_day(text: str) -> date:
    return datetime.strptime(text, "%Y%m%d").date()


def build_source(config, source_name: str):
    if source_name == "fixture":
        return FixtureClient(config.fixture_dir)
    if not config.kpx_api_key:
        raise SystemExit("KPX_API_KEY가 비어 있다. .env에 인증키를 넣거나 --source fixture를 쓰라.")
    return RecApiClient(
        base_url=config.kpx_base_url,
        service_key=config.kpx_api_key,
        budget=DailyBudget(limit=config.kpx_daily_budget),
    )


def cmd_gen_fixture(args, config) -> int:
    end = date.today()
    # 백필 시작일이 경계에 걸려 빈 날이 생기지 않도록 2주 여유를 둔다.
    start = end - timedelta(days=365 * args.years + 14)
    written = generate_fixtures(config.fixture_dir, start, end)
    print(f"fixture {written}개를 {config.fixture_dir}에 생성했다 ({start} ~ {end})")
    return 0


def cmd_collect(args, config) -> int:
    service = CollectorService(RecRepository(config.database_url), build_source(config, args.source))
    outcome = service.collect_day(parse_day(args.date), job_type="MANUAL")
    print(f"{outcome.trade_date} {outcome.status} rows={outcome.rows_upserted}")
    for issue in outcome.issues:
        print(f"  경고: {issue}")
    return 0 if outcome.status in {"SUCCESS", "PARTIAL", "NO_DATA"} else 1


def cmd_backfill(args, config) -> int:
    service = CollectorService(RecRepository(config.database_url), build_source(config, args.source))
    outcomes = service.backfill(parse_day(args.start), parse_day(args.end))
    summary: dict[str, int] = {}
    for outcome in outcomes:
        summary[outcome.status] = summary.get(outcome.status, 0) + 1
    print(f"{len(outcomes)}개 거래일 처리: {summary}")
    return 0


def cmd_probe(args, config) -> int:
    """실 API를 1회 호출해 원본 응답을 저장한다. 키 발급 직후 가장 먼저 실행한다."""
    client = build_source(config, "api")
    response = client.fetch(parse_day(args.date))

    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    target = SAMPLE_DIR / f"rec-{args.date}.json"
    target.write_text(json.dumps(response.payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"원본 응답을 {target}에 저장했다.")
    body = response.payload.get("response", {}).get("body", {})
    items = body.get("items")
    first = None
    if isinstance(items, dict):
        inner = items.get("item")
        first = inner[0] if isinstance(inner, list) and inner else inner
    if isinstance(first, dict):
        print("실제 item 필드명:")
        for key in sorted(first.keys()):
            print(f"  {key} = {first[key]!r}")
        print("\n이 목록에 맞게 rec/mapping.py의 FIELD_MAP과 AREA_MAP을 수정하라.")
    else:
        print("item이 비어 있다. 거래일이 아닌 날일 수 있으니 다른 날짜로 다시 시도하라.")
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    parser = argparse.ArgumentParser(prog="collector")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("gen-fixture", help="화·목 시계열 fixture 생성")
    gen.add_argument("--years", type=int, default=3)
    gen.set_defaults(func=cmd_gen_fixture)

    collect = sub.add_parser("collect", help="거래일 하나 수집")
    collect.add_argument("--date", required=True, help="YYYYMMDD")
    collect.add_argument("--source", choices=["api", "fixture"], default="fixture")
    collect.set_defaults(func=cmd_collect)

    backfill = sub.add_parser("backfill", help="구간 백필")
    backfill.add_argument("--from", dest="start", required=True, help="YYYYMMDD")
    backfill.add_argument("--to", dest="end", required=True, help="YYYYMMDD")
    backfill.add_argument("--source", choices=["api", "fixture"], default="fixture")
    backfill.set_defaults(func=cmd_backfill)

    probe = sub.add_parser("probe", help="실 API 원본 응답 덤프")
    probe.add_argument("--date", required=True, help="YYYYMMDD")
    probe.set_defaults(func=cmd_probe)

    args = parser.parse_args(argv)
    return args.func(args, load_config())


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: 테스트 통과 확인**

```powershell
docker compose run --rm collector-test
```

Expected: 모두 통과 (48 passed 내외)

- [ ] **Step 7: 커밋**

```powershell
cd C:\Dev\RECFlow
git add apps/collector
git commit -m "feat(collector): 서비스 조립과 CLI 추가

원본을 매핑보다 먼저 저장하므로 매핑이 실패해도 재처리로 복구된다.
검증 위반은 저장을 막지 않고 PARTIAL로 기록한다.
빈 응답은 NO_DATA로 확정해 누락일 재시도를 멈춘다.

probe 명령은 실 API 응답을 docs/api-samples에 덤프하고 실제 필드명을
출력한다. 키 발급 직후 가장 먼저 실행할 명령이다."
```

---

### Task 9: 3년치 백필 실행과 결과 검증

**Files:**
- Modify: `README.md`
- Create: `apps/collector/fixtures/` (생성물, `.gitignore`에 추가)
- Modify: `.gitignore`

**Interfaces:**
- Consumes: Task 8의 CLI
- Produces: `rec_market`에 약 930행(거래일 310 × 3개 구역)이 적재된 로컬 DB. 계획 B의 웹이 이 데이터를 읽는다.

- [ ] **Step 1: fixture를 git에서 제외**

`.gitignore`에 다음 두 줄을 추가한다. 생성물이며 seed로 언제든 재현되므로 커밋하지 않는다.

```text
# collector가 생성하는 fixture (seed로 재현 가능)
apps/collector/fixtures/
```

- [ ] **Step 2: 3년치 fixture 생성**

```powershell
cd C:\Dev\RECFlow
docker compose run --rm collector-test python -m cli gen-fixture --years 3
```

Expected: `fixture 31x개를 /app/fixtures에 생성했다 (2023-07-.. ~ 2026-08-12)` — 300~325 사이면 정상이다. 소스가 마운트되어 있으므로 호스트의 `apps/collector/fixtures/`에도 생성된다.

- [ ] **Step 3: 백필 실행**

```powershell
docker compose run --rm collector-test python -m cli backfill --from 20230812 --to 20260812 --source fixture
```

Expected: `31x개 거래일 처리: {'SUCCESS': 31x}` — `FAILED`가 하나라도 있으면 멈추고 원인을 조사한다. fixture 생성 구간이 백필 구간보다 2주 넓으므로 `NO_DATA`는 나오지 않아야 한다.

- [ ] **Step 4: 적재 결과 검증**

```powershell
docker exec recflow-db psql -U recflow -d recflow -c "SELECT market_area, COUNT(*) AS rows, MIN(trade_date) AS first_day, MAX(trade_date) AS last_day FROM rec_market GROUP BY market_area ORDER BY market_area;"
```

Expected: `LAND`, `JEJU`, `TOTAL` 각각 300~320행, 기간은 약 3년.

- [ ] **Step 5: 종가가 TOTAL에만 있는지 검증**

```powershell
docker exec recflow-db psql -U recflow -d recflow -c "SELECT market_area, COUNT(close_price) AS with_close, COUNT(trade_amount) AS with_amount FROM rec_market GROUP BY market_area ORDER BY market_area;"
```

Expected: `TOTAL`만 0보다 크고 `LAND`/`JEJU`는 둘 다 0이다. 설계상 종가·거래금액은 통합값으로만 제공되기 때문이다.

- [ ] **Step 6: UPSERT 멱등성 재확인**

```powershell
docker compose run --rm collector-test python -m cli collect --date 20260806 --source fixture
docker exec recflow-db psql -U recflow -d recflow -c "SELECT COUNT(*) FROM rec_market WHERE trade_date = '2026-08-06';"
```

Expected: 3 — 재수집해도 3행 그대로다.

- [ ] **Step 7: 실행 이력 확인**

```powershell
docker exec recflow-db psql -U recflow -d recflow -c "SELECT status, COUNT(*) FROM collection_runs GROUP BY status;"
```

Expected: 대부분 `SUCCESS`. `FAILED`가 있으면 `error_message`를 확인한다.

- [ ] **Step 8: README에 수집기 사용법 추가**

`README.md`의 `## 구성` 섹션 앞에 다음을 삽입한다.

````markdown
## 수집기 사용법

파이썬은 컨테이너(3.12) 안에서만 실행한다. 호스트에 가상환경을 만들지 않는다.

```powershell
# 테스트
docker compose run --rm collector-test

# API 키가 없는 동안: fixture로 3년치 데이터 만들고 적재
docker compose run --rm collector-test python -m cli gen-fixture --years 3
docker compose run --rm collector-test python -m cli backfill --from 20230812 --to 20260812 --source fixture
```

### API 키가 발급되면

1. `.env`의 `KPX_API_KEY`에 일반 인증키(Decoding)를 넣는다.
2. 실제 응답을 덤프하고 필드명을 확인한다.

   ```powershell
   docker compose run --rm collector-test python -m cli probe --date <최근 화요일 또는 목요일 YYYYMMDD>
   ```

3. 출력된 필드명에 맞게 `apps/collector/rec/mapping.py`의 `FIELD_MAP`과 `AREA_MAP`을 수정한다.
4. `tests/samples/rec_response_sample.json`을 실제 응답으로 교체하고 테스트를 다시 돌린다.
5. fixture로 넣은 데이터를 지우고 실 데이터로 백필한다.

   ```powershell
   docker exec recflow-db psql -U recflow -d recflow -c "DELETE FROM rec_market WHERE source = 'fixture';"
   docker compose run --rm collector-test python -m cli backfill --from <시작일> --to <종료일> --source api
   ```

   개발계정은 하루 100건으로 제한되므로 3년치 백필은 며칠에 나뉘어 진행된다.
   예산이 소진되면 자동으로 중단하고 다음 실행에서 남은 구간부터 이어받는다.
````

- [ ] **Step 9: 커밋**

```powershell
cd C:\Dev\RECFlow
git add .gitignore README.md
git commit -m "docs: 수집기 사용법과 API 키 전환 절차 추가

fixture 3년치를 생성해 백필한 결과를 검증했다. 거래일 약 310일 ×
3개 구역이 적재되고, 종가와 거래금액은 TOTAL 행에만 채워진다.

fixture 디렉토리는 seed로 재현 가능한 생성물이므로 커밋하지 않는다."
```

---

### Task 10: 스케줄러, 내부 API, 컨테이너화

**Files:**
- Create: `apps/collector/jobs/__init__.py`
- Create: `apps/collector/jobs/scheduler.py`
- Create: `apps/collector/api.py`
- Create: `apps/collector/tests/test_api.py`
- Modify: `docker-compose.yml` (`collector` 서비스 추가)

`Dockerfile`과 `.dockerignore`는 Task 3에서 이미 만들었으므로 여기서 다시 만들지 않는다.

**Interfaces:**
- Consumes: Task 8의 `CollectorService`, `load_config`
- Produces:
  - `build_scheduler(service) -> BackgroundScheduler` — 화·목 16:30 `SCHEDULED`, 화·목 18:00 `RECHECK`, 매일 09:00 `GAP_SCAN`
  - FastAPI 앱: `GET /health` → `{"status": "ok", "lastSuccessfulRun": {...} | null}`, `POST /jobs/collect` → 수집 결과
  - `recflow-collector` 컨테이너 (compose 내부 네트워크 전용)

- [ ] **Step 1: API 테스트 작성**

`apps/collector/tests/test_api.py`:

```python
from datetime import date

import pytest
from fastapi.testclient import TestClient

from api import create_app
from rec.fixture_client import FixtureClient, generate_fixtures
from rec.service import CollectorService


@pytest.fixture
def client(repo, tmp_path):
    generate_fixtures(tmp_path, date(2026, 7, 1), date(2026, 8, 6))
    service = CollectorService(repo, FixtureClient(tmp_path))
    return TestClient(create_app(service=service, repository=repo))


def test_health_reports_ok_with_no_runs(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["lastSuccessfulRun"] is None


def test_health_reports_last_successful_run(client):
    client.post("/jobs/collect", json={"tradeDate": "2026-08-06"})
    body = client.get("/health").json()
    assert body["lastSuccessfulRun"]["targetDate"] == "2026-08-06"


def test_collect_job_returns_outcome(client):
    response = client.post("/jobs/collect", json={"tradeDate": "2026-08-06"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "SUCCESS"
    assert body["rowsUpserted"] == 3


def test_collect_job_rejects_bad_date(client):
    assert client.post("/jobs/collect", json={"tradeDate": "not-a-date"}).status_code == 422
```

- [ ] **Step 2: 테스트 실패 확인**

```powershell
docker compose run --rm collector-test python -m pytest tests/test_api.py -v
```

`TestClient`는 `httpx`를 쓰는데 이미 `requirements.txt`에 있으므로 추가 설치가 필요 없다.

Expected: FAIL — `ModuleNotFoundError: No module named 'api'`

- [ ] **Step 3: `jobs/scheduler.py` 구현**

```python
"""정기 수집 스케줄.

REC 현물시장은 매주 화·목 10:00~16:00에 운영되므로 장 종료 이후에 수집한다.
타임존은 Asia/Seoul로 고정한다. 호스트 cron에 의존하지 않으므로 서버를
옮겨도 동작이 같다.
"""

from __future__ import annotations

import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from rec.service import CollectorService

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")


def build_scheduler(service: CollectorService) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=KST)

    scheduler.add_job(
        lambda: _collect_today(service, "SCHEDULED"),
        CronTrigger(day_of_week="tue,thu", hour=16, minute=30, timezone=KST),
        id="rec-scheduled",
        replace_existing=True,
    )
    scheduler.add_job(
        lambda: _collect_today(service, "RECHECK"),
        CronTrigger(day_of_week="tue,thu", hour=18, minute=0, timezone=KST),
        id="rec-recheck",
        replace_existing=True,
    )
    scheduler.add_job(
        lambda: _scan_gaps(service),
        CronTrigger(hour=9, minute=0, timezone=KST),
        id="rec-gap-scan",
        replace_existing=True,
    )
    return scheduler


def _collect_today(service: CollectorService, job_type: str) -> None:
    from datetime import datetime

    today = datetime.now(KST).date()
    logger.info("%s 수집 시작 (%s)", today, job_type)
    outcome = service.collect_day(today, job_type=job_type)
    logger.info("%s 수집 종료: %s rows=%d", today, outcome.status, outcome.rows_upserted)


def _scan_gaps(service: CollectorService) -> None:
    logger.info("누락일 점검 시작")
    outcomes = service.scan_gaps(days=30)
    logger.info("누락일 점검 종료: %d건 처리", len(outcomes))
```

- [ ] **Step 4: `api.py` 구현**

```python
"""수집기 내부 전용 HTTP API.

Docker 내부 네트워크에서만 접근 가능하며 Caddy에 연결하지 않는다.
웹 관리자 화면이 수집 상태 확인과 수동 재수집에 사용한다.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI
from pydantic import BaseModel

from config import load_config
from jobs.scheduler import build_scheduler
from rec.fixture_client import FixtureClient
from rec.repository import RecRepository
from rec.service import CollectorService

logger = logging.getLogger(__name__)


class CollectRequest(BaseModel):
    tradeDate: date


def create_app(service: CollectorService, repository: RecRepository, scheduler=None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if scheduler is not None:
            scheduler.start()
            logger.info("스케줄러를 시작했다")
        yield
        if scheduler is not None:
            scheduler.shutdown(wait=False)

    app = FastAPI(title="RECFlow Collector", lifespan=lifespan)

    @app.get("/health")
    def health() -> dict:
        last = repository.last_successful_run()
        return {
            "status": "ok",
            "lastSuccessfulRun": None
            if last is None
            else {
                "targetDate": last["target_date"].isoformat() if last["target_date"] else None,
                "jobType": last["job_type"],
                "rowsUpserted": last["rows_upserted"],
                "finishedAt": last["finished_at"].isoformat() if last["finished_at"] else None,
            },
        }

    @app.post("/jobs/collect")
    def collect(request: CollectRequest) -> dict:
        outcome = service.collect_day(request.tradeDate, job_type="MANUAL")
        return {
            "tradeDate": outcome.trade_date.isoformat(),
            "status": outcome.status,
            "rowsUpserted": outcome.rows_upserted,
            "issues": outcome.issues,
        }

    return app


def build_default_app() -> FastAPI:
    """컨테이너 진입점. 설정에 따라 실 API 또는 fixture 소스를 고른다."""
    config = load_config()
    repository = RecRepository(config.database_url)

    if config.kpx_api_key:
        from rec.budget import DailyBudget
        from rec.client import RecApiClient

        source = RecApiClient(
            base_url=config.kpx_base_url,
            service_key=config.kpx_api_key,
            budget=DailyBudget(limit=config.kpx_daily_budget),
        )
        logger.info("실 API 소스를 사용한다")
    else:
        source = FixtureClient(config.fixture_dir)
        logger.warning("KPX_API_KEY가 없어 fixture 소스로 기동한다")

    service = CollectorService(repository, source)
    return create_app(service=service, repository=repository, scheduler=build_scheduler(service))
```

- [ ] **Step 5: 테스트 통과 확인**

```powershell
docker compose run --rm collector-test python -m pytest tests/test_api.py -v
```

Expected: 4 passed

- [ ] **Step 6: compose에 collector 추가**

`docker-compose.yml`의 `services:` 아래, `volumes:` 위에 다음을 추가한다.

```yaml
  collector:
    build: ./apps/collector
    container_name: recflow-collector
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
      KPX_API_KEY: ${KPX_API_KEY}
      KPX_BASE_URL: ${KPX_BASE_URL}
      KPX_DAILY_BUDGET: ${KPX_DAILY_BUDGET}
      FIXTURE_DIR: /app/fixtures
      TZ: ${TZ}
    volumes:
      - collector_fixtures:/app/fixtures
    # 포트를 호스트에 노출하지 않는다. 내부 네트워크 전용이다.
```

`volumes:` 블록에 항목을 추가한다.

```yaml
volumes:
  postgres_data:
  collector_fixtures:
```

- [ ] **Step 7: 컨테이너 기동 검증**

```powershell
cd C:\Dev\RECFlow
docker compose up -d --build collector
docker compose logs collector --tail 30
```

Expected: 로그에 `KPX_API_KEY가 없어 fixture 소스로 기동한다`와 `스케줄러를 시작했다`, `Uvicorn running on http://0.0.0.0:8000`이 보인다.

- [ ] **Step 8: 내부 API 동작 확인**

```powershell
docker compose exec collector python -c "import urllib.request, json; print(json.load(urllib.request.urlopen('http://localhost:8000/health')))"
```

Expected: `{'status': 'ok', 'lastSuccessfulRun': {...}}`

- [ ] **Step 9: 포트가 외부에 노출되지 않았는지 확인**

```powershell
docker compose ps
```

Expected: `collector`의 PORTS 칸이 비어 있거나 `8000/tcp`만 표시되고 `0.0.0.0:8000->` 매핑이 없다. 매핑이 있으면 compose에서 `ports:`를 제거한다.

- [ ] **Step 10: 전체 테스트 최종 확인**

```powershell
cd C:\Dev\RECFlow
docker compose run --rm collector-test
```

Expected: 전부 통과

- [ ] **Step 11: 커밋**

```powershell
cd C:\Dev\RECFlow
git add apps/collector docker-compose.yml
git commit -m "feat(collector): 스케줄러, 내부 API, 컨테이너화

APScheduler를 컨테이너 안에서 Asia/Seoul 고정으로 구동한다.
화·목 16:30 수집, 18:00 재확인, 매일 09:00 누락일 점검.

FastAPI는 health와 수동 수집 두 엔드포인트만 제공하며 호스트 포트를
노출하지 않는다. 웹 관리자 화면이 Docker 내부 네트워크로 호출한다.

KPX_API_KEY가 비어 있으면 fixture 소스로 기동하므로 키 없이도
전체 파이프라인이 돌아간다."
```

---

## 완료 기준

계획 A는 아래가 모두 참일 때 완료된다.

1. `docker compose run --rm collector-test`가 전부 통과한다.
2. `rec_market`에 3개 구역 × 약 310 거래일이 적재되어 있다.
3. 같은 거래일을 재수집해도 행 수가 늘지 않는다.
4. `close_price`와 `trade_amount`가 `TOTAL` 행에만 채워져 있다.
5. `docker compose up -d`로 db와 collector가 모두 뜨고, collector의 8000 포트가 호스트에 노출되지 않는다.
6. `mapping.py` 밖의 어떤 파일에도 API 필드 문자열(`tradeDay`, `avgPrice` 등)이 없다.
7. `README.md`에 API 키 발급 후 전환 절차가 적혀 있다.

## 계획 A에서 하지 않는 것

- 웹 UI, Prisma Client 사용 코드 (계획 B)
- Caddy, 운영 compose, pg_dump 백업 (계획 C)
- SMP 수집, Telegram 알림, `alerts` 테이블 (Phase 4)
- 실 API 호출 (키 발급 후 `probe`로 시작)
