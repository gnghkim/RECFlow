# REC 가격추적 시스템 설계문서

- 작성일: 2026-08-12
- 근거 문서: `REC_가격추적_시스템_구현계획서.md`
- 범위: 계획서 18장 기준 **Phase 1~3**
- 리포지토리: `C:\Dev\RECFlow` (RECFlow)

---

## 1. 목적과 범위

법인이 보유한 태양광 REC의 시장가격을 자동 수집·축적하고, 보유 REC 평가액과 매각 시뮬레이션,
설명 가능한 매각 판단 지표를 제공하는 사내 전용 웹 시스템을 구축한다.

### 이번 범위에 포함

| Phase | 내용 |
|---|---|
| 1 | Docker 환경, PostgreSQL, REC 수집, 가격 DB, 대시보드, 가격·거래량 차트, 기간별 조회 |
| 2 | 발전소 관리, REC 보유량, 매각내역, 현재 평가금액, 목표가격, 매각 시뮬레이션 |
| 3 | 이동평균, 1년 Percentile, 가격 위치, 거래량 분석, 매각 판단 점수, 분할매각 시뮬레이션 |

### 이번 범위에서 제외

- SMP 수집·연계 (Phase 4)
- Telegram 알림, `alerts` 테이블 (Phase 4)
- 발전량·기상정보 연계 (Phase 5)
- AI 가격예측, 머신러닝, 실시간 WebSocket, 모바일 앱, 다중 권한관리 (계획서 19장)
- E2E 테스트

제외된 항목은 이번 스키마와 코드에 자리를 만들어두지 않는다. 필요해지면 마이그레이션과 모듈을 추가한다.

---

## 2. 전제 조건과 현재 상태

| 항목 | 상태 | 설계에 미치는 영향 |
|---|---|---|
| Ubuntu VPS | **보유** | 배포 대상 존재. prod compose와 배포 문서를 이번 범위에 포함 |
| 공공데이터포털 API 키 | **미보유** | 실제 응답 필드를 확정할 수 없음 → 어댑터 + probe 구조 필요 |
| 로컬 환경 | Windows 11, Node 24, Python 3.14, Git, Docker Desktop(정지 상태) | 로컬 개발은 Docker Compose 기동 필요 |
| 인증 요구 | 단일 비밀번호 로그인 | 사용자 테이블·가입·비밀번호 재설정 없음 |
| 보유 REC 저장 기준 | **가중치가 이미 적용된 발급 REC 수량** | 평가액 = 보유 REC × 시장가격. 시스템이 가중치를 곱하지 않는다 |

### 확인된 외부 API 사실 (공개 명세 기준)

- 데이터셋: 공공데이터포털 「한국전력거래소_REC 현물시장 정보」 (`data.go.kr/data/15099762`)
- 유형 REST, 포맷 JSON+XML, 무료
- 요청 변수: `serviceKey`, `pageNo`, `numOfRows`, `dataType`, `tradeDay`
- 트래픽: **개발계정 100건/일**, 운영계정은 활용사례 등록 후 증량 신청
- 승인: 개발단계 자동승인 / 운영단계 심의승인
- 제공 값: 거래건수, 거래량, 평균가, 최고가, 최저가, 종가, 거래금액, 육지/제주 구분
- **종가와 거래금액은 육지·제주 통합값**으로 제공된다

### 확정되지 않은 사실

**응답 필드의 영문 키 이름은 공개 페이지에서 확인되지 않는다.** 추정하지 않는다.
키 발급 후 `probe` 명령으로 실제 응답을 덤프하여 확정한다 (계획서 22장 원칙).

---

## 3. 아키텍처

```text
KPX Open API
     │
     ▼
 collector (Python)
   client → mapping → service → repository
     │                   │
     │                   └── 원본 JSON + 실행이력 저장
     ▼
 PostgreSQL
     ▲
     │ (Prisma)
 web (Next.js)
     ▲
     │ (HTTPS)
   Caddy ──▶ 인터넷
```

- **웹만 외부에 노출**된다. collector와 Postgres는 Docker 내부 네트워크에만 존재한다.
- PostgreSQL 5432 포트는 호스트에 바인딩하지 않는다 (로컬 개발 시에만 바인딩).
- collector는 웹의 요청 경로에 끼어들지 않는다. 웹은 DB만 읽는다 (계획서 20.2).

### 리포지토리 구조

```text
C:\Dev\RECFlow\
├─ apps/
│  ├─ web/                    Next.js 15 App Router + TypeScript
│  │  ├─ app/
│  │  │  ├─ login/
│  │  │  ├─ (app)/            dashboard, market, inventory, simulation, settings, admin
│  │  │  └─ api/
│  │  ├─ components/
│  │  ├─ lib/
│  │  │  ├─ db.ts
│  │  │  ├─ auth.ts
│  │  │  └─ analytics/        ma.ts, percentile.ts, score.ts, simulation.ts, valuation.ts
│  │  └─ package.json
│  └─ collector/              Python 3.12
│     ├─ rec/
│     │  ├─ client.py         HTTP·재시도·타임아웃·일일예산
│     │  ├─ fixture_client.py fixture 소스 (client와 동일 인터페이스)
│     │  ├─ mapping.py        원본 dict → 도메인 dataclass  ★필드명을 아는 유일한 파일
│     │  ├─ models.py         도메인 dataclass
│     │  ├─ repository.py     UPSERT·원본저장·실행이력
│     │  └─ service.py        조립
│     ├─ jobs/scheduler.py    APScheduler
│     ├─ api.py               내부 전용 FastAPI
│     ├─ cli.py               probe / collect / backfill / gen-fixture
│     ├─ fixtures/
│     ├─ tests/
│     └─ requirements.txt
├─ prisma/schema.prisma
├─ infra/
│  ├─ caddy/Caddyfile
│  ├─ backup/
│  └─ scripts/
├─ docker-compose.yml         로컬 개발
├─ docker-compose.prod.yml    VPS 운영 (Caddy 포함)
├─ .env.example
├─ README.md
└─ docs/
   ├─ deployment.md
   └─ superpowers/specs/
```

### 경계 결정

**1. 스키마 소유권은 Prisma 단독.**
마이그레이션은 Prisma만 생성·적용한다. Python collector는 `psycopg`로 이미 존재하는 테이블에
SQL을 실행할 뿐이며, 어떤 DDL도 실행하지 않는다. 스키마 정의가 두 곳에 있으면 반드시 어긋난다.

**2. API 필드명을 아는 파일은 `rec/mapping.py` 하나뿐.**
`client`는 HTTP만, `repository`는 DB만, `service`는 조립만 안다. 세 모듈은 도메인 dataclass로
대화한다. 키 발급 후 필드가 확정되면 `mapping.py`만 수정하면 되고, 향후 API 스펙이 바뀌어도
수정 범위가 한 파일로 격리된다.

**3. collector는 컨테이너 내부에서 스스로 스케줄링하고, 내부 전용 HTTP를 제공한다.**
호스트 cron에 의존하지 않고 APScheduler(Asia/Seoul 고정)를 사용한다. 함께 띄우는 FastAPI는
`GET /health`와 `POST /jobs/collect` 두 엔드포인트만 가지며, Docker 내부 네트워크에서만 접근
가능하다. Caddy에 연결하지 않는다. 웹 관리자 화면이 이를 호출해 수동 재수집(계획서 6.3)을
수행하고 수집 상태(계획서 17장)를 표시한다.

**4. 분석 로직은 순수 함수로 격리한다.**
이동평균·Percentile·매각점수·시뮬레이션은 `apps/web/lib/analytics/`에 입출력만 있는 함수로 두고,
DB와 React를 알지 못하게 한다. 금액과 의사결정이 걸린 부분이므로 테스트의 중심이 된다.

---

## 4. 데이터베이스 스키마

계획서 20.1에 따라 **시장 데이터와 회사 데이터를 분리**한다. 외부 API 구조가 바뀌어도 회사
데이터는 영향을 받지 않는다.

모든 가격·수량·금액 컬럼은 `Decimal`(PostgreSQL `numeric`)을 사용한다. 부동소수점을 쓰지 않는다.

### 4.1 시장 데이터

#### `rec_market`

거래일별 REC 현물시장 시세.

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `id` | Int PK | |
| `trade_date` | Date | |
| `market_area` | Enum `LAND` \| `JEJU` \| `TOTAL` | |
| `trade_count` | Int? | |
| `volume` | Decimal(14,2)? | |
| `avg_price` | Decimal(12,2)? | |
| `high_price` | Decimal(12,2)? | |
| `low_price` | Decimal(12,2)? | |
| `close_price` | Decimal(12,2)? | 통합값만 제공 → `TOTAL` 행에만 채워짐 |
| `trade_amount` | Decimal(18,2)? | 통합값만 제공 → `TOTAL` 행에만 채워짐 |
| `source` | String | 예: `kpx-openapi`, `fixture` |
| `created_at` / `updated_at` | DateTime | |

제약: `@@unique([trade_date, market_area])` — UPSERT 키 (계획서 6.1)

수치 컬럼을 nullable로 두는 이유는 육지/제주 행에서 종가·거래금액이 제공되지 않기 때문이다.
값이 없는 것과 0인 것을 구분해야 하며, 화면은 없는 값을 `—`로 표시한다.

#### `rec_market_raw`

API 원본 보존 (계획서 20.3).

| 컬럼 | 타입 |
|---|---|
| `id` | Int PK |
| `trade_date` | Date |
| `endpoint` | String |
| `http_status` | Int |
| `payload` | Json |
| `fetched_at` | DateTime |
| `collection_run_id` | Int FK → `collection_runs` |

**원본은 매핑보다 먼저 저장한다.** 매핑이 실패해도 원본은 남으므로 재처리로 복구할 수 있다.

#### `collection_runs`

수집 실행 이력. 계획서 6.3의 "마지막 정상 수집시간 저장"과 17장 운영 모니터링의 데이터 원천.

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `id` | Int PK | |
| `job_type` | Enum `SCHEDULED` \| `RECHECK` \| `BACKFILL` \| `MANUAL` \| `GAP_SCAN` | |
| `target_date` | Date? | |
| `status` | Enum `SUCCESS` \| `PARTIAL` \| `NO_DATA` \| `FAILED` | |
| `attempts` | Int | |
| `rows_upserted` | Int | |
| `error_message` | String? | |
| `started_at` / `finished_at` | DateTime | |

`NO_DATA`는 휴장일로 판단되어 재시도를 중단한 상태를 뜻한다.

### 4.2 회사 데이터

#### `plants`

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `id` | Int PK | |
| `name` | String | |
| `location` | String? | |
| `capacity_kw` | Decimal(12,2)? | |
| `operation_date` | Date? | |
| `rec_weight` | Decimal(4,2)? | 참고값. 평가액 계산에 사용하지 않음 |
| `is_active` | Boolean | 기본 `true` |
| `created_at` / `updated_at` | DateTime | |

`rec_weight`는 향후 발전량 → REC 예측(Phase 5)을 위한 기록용이다. **이번 범위의 어떤 계산식에도
등장하지 않는다.**

#### `rec_inventory`

REC 발급 이력.

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `id` | Int PK | |
| `plant_id` | Int FK → `plants` | |
| `issue_date` | Date | |
| `rec_quantity` | Decimal(14,2) | **가중치가 적용된 발급 REC 수량** |
| `expired_at` | Date? | 소멸 처리일 |
| `memo` | String? | |
| `created_at` / `updated_at` | DateTime | |

**계획서 7.3에서 변경한 점: `status (HELD/SOLD/EXPIRED)` 컬럼을 제거한다.**

- 이유: 발급 로트를 부분 매각하면 status 한 값으로 표현할 수 없다. 또한 `rec_sales`와 이중
  기록이 되어 시간이 지나면 반드시 어긋난다.
- 대체: **보유량을 파생 계산한다.** 정확한 정의는 다음과 같다.

  ```text
  발급 = Σ rec_inventory.rec_quantity                (expired_at IS NULL)
  매각 = Σ rec_sales.quantity
  보유 = 발급 − 매각
  ```

  소멸된 로트는 `expired_at`이 채워지며 발급 합계에서 빠진다. 진실의 원천이 하나가 되고,
  계획서 8.5의 표(발급/매각/보유)와 정확히 같은 식이 된다.
- 발급과 매각은 각각 `plant_id`를 가지므로 발전소별 집계도 같은 식으로 산출한다.

#### `rec_sales`

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `id` | Int PK | |
| `plant_id` | Int FK → `plants` | |
| `sale_date` | Date | |
| `quantity` | Decimal(14,2) | |
| `unit_price` | Decimal(12,2) | |
| `sale_amount` | Decimal(18,2) | 실제 정산금액. 기본값은 `quantity × unit_price`이나 반올림 차이를 허용하기 위해 저장한다 |
| `buyer` | String? | |
| `memo` | String? | |
| `created_at` | DateTime | |

#### `price_targets`

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `id` | Int PK | |
| `name` | String | 예: "1차 매도 검토" |
| `target_price` | Decimal(12,2) | |
| `is_active` | Boolean | 기본 `true` |
| `created_at` / `updated_at` | DateTime | |

이번 범위에서는 **표시·시뮬레이션 기준값**으로만 쓰인다. 알림 관련 컬럼(`alert_enabled`,
`alert_type`)은 Phase 4에 추가한다.

### 4.3 이번 범위에 만들지 않는 테이블

`smp_daily`, `alerts` — Phase 4에서 마이그레이션으로 추가한다.

인증은 서명 쿠키 기반 무상태 방식이므로 사용자·세션 테이블이 없다.

---

## 5. 수집기 설계

### 5.1 모듈 책임

| 모듈 | 아는 것 | 모르는 것 |
|---|---|---|
| `client.py` | HTTP, 재시도, 타임아웃, 일일 예산, `serviceKey` | DB, 응답 필드 의미 |
| `fixture_client.py` | fixture 파일 읽기 | 위와 동일. `client.py`와 같은 인터페이스 |
| `mapping.py` | **API 응답 필드명** | HTTP, DB |
| `repository.py` | SQL, UPSERT, 원본저장, 실행이력 | HTTP, 응답 필드 |
| `service.py` | 위 모듈의 조립 순서 | 각 모듈의 내부 |

### 5.2 스케줄 (Asia/Seoul 고정)

| 시각 | 작업 | `job_type` |
|---|---|---|
| 화·목 16:30 | 당일 수집 | `SCHEDULED` |
| 화·목 18:00 | 당일 재확인 | `RECHECK` |
| 매일 09:00 | 최근 30일 누락일 점검 및 재수집 | `GAP_SCAN` |

APScheduler를 collector 컨테이너 안에서 구동한다. 호스트 cron에 의존하지 않으므로 VPS를 옮겨도
동작이 동일하다.

### 5.3 신뢰성

- **타임아웃**: connect 5초 / read 20초
- **재시도**: 최대 3회, 지수 백오프 2s → 8s → 32s. 5xx와 네트워크 오류만 재시도하고 4xx는
  즉시 실패 처리한다
- **일일 예산**: 개발계정 100건/일에 맞춰 **하루 80건**으로 자체 제한한다. 예산 소진 시 남은
  작업을 중단하고 `collection_runs`에 진행 지점을 남긴다
- **백필**: 3년치는 화·목 기준 약 310 거래일이므로 일일 예산 안에서 며칠에 걸쳐 진행된다.
  마지막 성공 지점부터 이어받는다
- **UPSERT**: `ON CONFLICT (trade_date, market_area) DO UPDATE`. 같은 거래일을 몇 번 수집해도
  행이 늘지 않는다
- **원본 우선 저장**: 매핑 실패 여부와 무관하게 원본을 먼저 저장한다
- **검증**: 아래 조건 위반 시 저장은 하되 `status = PARTIAL`로 기록하고 관리자 화면에 노출한다
  - 평균가 / 종가가 최저가~최고가 범위 밖
  - 거래량 또는 거래금액이 음수
  - 가격이 0 이하
- **휴장일 처리**: 화·목이라도 공휴일에는 데이터가 없다. 공휴일 API를 추가로 연동하지 않고,
  3회 재시도 후에도 빈 응답이면 `NO_DATA`로 마킹하여 `GAP_SCAN`의 무한 재시도를 멈춘다

### 5.4 CLI

```text
python -m collector.cli probe --date YYYYMMDD
    실제 API를 1회 호출하여 원본 응답을 apps/collector/api-samples/rec-YYYYMMDD.json 에 저장하고
    최상위 필드 목록을 출력한다. 키 발급 직후 가장 먼저 실행한다.

python -m collector.cli collect --date YYYYMMDD [--source api|fixture]
python -m collector.cli backfill --from YYYYMMDD --to YYYYMMDD [--source api|fixture]
python -m collector.cli gen-fixture --years 3
    화·목 3년치 시계열 fixture를 생성한다.
```

### 5.5 API 키 없이 개발하는 방법

`--source=fixture`는 **client 계층만** 교체한다. mapping → 검증 → 원본저장 → UPSERT →
실행이력 기록은 실제와 동일한 경로를 지난다. 따라서 fixture로 통과한 파이프라인은 키가 생겨도
그대로 동작하며, 바꿔야 하는 것은 `mapping.py`뿐이다.

fixture 생성기는 실제 REC 가격대(6만~8만원)와 주 2회 거래 리듬을 흉내낸 3년치 시계열을
만들어, 이동평균·Percentile·차트·시뮬레이션을 실제와 유사한 조건에서 개발할 수 있게 한다.

---

## 6. 웹 애플리케이션

### 6.1 화면

| 경로 | 내용 | 계획서 |
|---|---|---|
| `/login` | 단일 비밀번호 입력 | — |
| `/dashboard` | 최근 거래일 요약, 가격추이 차트, 보유REC·평가액, 매각 판단 | 8.1 |
| `/market` | 시세 지표, 기간별 통계, 가격/거래량/이동평균/분포 차트, 가격 위치 | 8.2~8.4 |
| `/inventory` | 발전소 관리, 발급 이력, 매각 내역, 발전소별 보유·평가액 | 8.5 |
| `/simulation` | 목표가별 매출표, 분할매각 시뮬레이션 | 8.6~8.7 |
| `/settings` | 목표가격 관리 | 7.6 |
| `/admin` | 수집 상태, 최근 실행 이력, 수동 재수집 | 17장 |

기간 선택은 `1M / 3M / 6M / 1Y / 3Y / ALL`을 공통 컴포넌트로 제공한다.

### 6.2 인증

- `APP_PASSWORD` 환경변수와 `timingSafeEqual`로 비교한다
- 성공 시 `jose`로 HS256 서명한 JWT를 httpOnly · SameSite=Lax · Secure 쿠키에 담는다
  (서명 키는 `AUTH_SECRET`)
- Next.js middleware가 `/login`과 정적 자산을 제외한 모든 경로를 차단한다
- 로그인 시도는 IP당 분당 5회로 제한한다 (인메모리 카운터)
- 사용자 테이블, 가입, 비밀번호 재설정, 역할 구분은 만들지 않는다

### 6.3 API 라우트

계획서 12장을 따른다. 조회는 Server Component에서 Prisma로 직접 수행하고, 아래 라우트는
클라이언트 상호작용(기간 변경, CRUD, 시뮬레이션)에 사용한다.

```text
GET    /api/rec/latest        GET  /api/rec/history      GET /api/rec/stats
GET    /api/inventory         POST /api/inventory        PATCH/DELETE /api/inventory/:id
GET    /api/plants            POST /api/plants           PATCH/DELETE /api/plants/:id
GET    /api/sales             POST /api/sales
GET    /api/targets           POST /api/targets          PATCH/DELETE /api/targets/:id
POST   /api/simulation
GET    /api/admin/status      POST /api/admin/collect
```

`/api/smp/*`는 Phase 4에서 추가한다.

### 6.4 분석 로직

`apps/web/lib/analytics/` — DB와 React를 모르는 순수 함수.

**기준 시장 구분**: 대시보드의 요약 지표, 이동평균, Percentile, 매각 판단 점수, 평가액은 모두
`market_area = TOTAL` 행을 기준으로 계산한다. 종가·거래금액이 통합값으로만 제공되므로 이것이
유일하게 모든 컬럼이 채워지는 계열이다. `LAND` / `JEJU`는 `/market` 화면에서 비교 목적으로만
표시한다.

| 함수 | 정의 |
|---|---|
| `movingAverage(series, n)` | **거래일 인덱스 기준** 단순이동평균. 주 2회 거래이므로 캘린더 기준이 아니다. MA4/8/26/52/104 (계획서 8.3) |
| `percentile(current, window)` | `(window 중 current 이하인 값의 개수 / window 길이) × 100`. 동점은 "이하"에 산입한다. 1년 Percentile의 window는 `trade_date`가 최근 365일 이내인 `TOTAL` 행의 `avg_price` 배열이며, 최소 26개 미만이면 `null` |
| `priceBand(percentile)` | 0–20 매우 낮음 / 20–40 낮음 / 40–60 보통 / 60–80 높음 / 80–100 매우 높음 (계획서 8.4) |
| `decisionScore(input)` | 계획서 9장 규칙. `{ total, breakdown: { position, trend, volume }, label }` 반환 |
| `valuation(holdings, price)` | 평가액 |
| `simulate(quantity, prices[])` | 목표가별 예상매출과 현재가 대비 증감 (계획서 8.6) |
| `simulateTranches(tranches[])` | 분할매각 총매출과 **가중평균** 매도가 (계획서 8.7) |

#### 데이터 부족 처리 규칙

**계산에 필요한 거래일 수가 부족하면 0이나 직전값이 아니라 `null`을 반환하고, 화면은 `—`와
사유를 표시한다.**

시스템 가동 초기 몇 주 동안 MA52·MA104·1년 Percentile은 필연적으로 계산 불가 상태다. 이를
0이나 앞값 복제로 채우면 매각 판단 점수가 조용히 틀린 값을 내놓는다. 이 시스템의 최악의 실패
모드는 잘못된 확신을 주는 것이므로, 계산 불가를 명시적으로 드러낸다.

`decisionScore`도 마찬가지로 구성요소 중 하나라도 계산 불가면 해당 항목을 `null`로 두고,
총점 대신 "데이터 부족"을 표시한다.

#### 금액 정밀도

DB `numeric` → 서버에서 `Decimal`로 합산 → 화면 전달 시 문자열. 차트 좌표 계산에만 `number`로
변환한다. 부동소수점 오차가 금액에 닿지 않게 한다.

### 6.5 빈 상태 처리

수집 데이터가 하나도 없는 최초 기동 상태를 1급 상태로 다룬다. 대시보드는 오류를 던지지 않고
"수집된 데이터가 없습니다"와 다음 행동(관리자 화면에서 수동 수집)을 안내한다.

---

## 7. 테스트 전략

| 대상 | 방식 | 중점 |
|---|---|---|
| `lib/analytics/*` | Vitest, **TDD** | 데이터 부족, 동점, 데이터 1개, 반올림, 음수·0 방어 |
| `collector/rec/mapping.py` | pytest 골든 테스트 | 저장된 실제 API 샘플 JSON 기준. 필드 누락 시 명확한 예외 |
| `collector/rec/repository.py` | pytest + 실제 Postgres | 같은 거래일 2회 적재 시 행이 늘지 않는지 (UPSERT) |
| `collector/rec/client.py` | pytest + HTTP 목 | 재시도 횟수, 백오프, 4xx 즉시 실패, 일일 예산 소진 |
| 통합 | fixture 3년치 백필 후 대시보드 렌더 | 실제 파이프라인 전체 경로 |

E2E 테스트는 이번 범위에서 만들지 않는다.

---

## 8. 인프라와 운영

### 8.1 Docker 구성

`docker-compose.yml` (로컬): `db`, `collector`, `web`
`docker-compose.prod.yml` (VPS): 위 + `caddy`, `db-backup`

- `db`: PostgreSQL. 로컬에서만 호스트 포트를 바인딩하고 운영에서는 바인딩하지 않는다
- `collector`: APScheduler + FastAPI. 내부 네트워크 전용
- `web`: Next.js standalone 빌드
- `caddy`: 80/443, 자동 HTTPS, `rec.<도메인>` → `web`
- `db-backup`: `pg_dump` 일 1회 02:00

향후 다른 사내 서비스를 같은 VPS에 올릴 수 있도록, Caddy와 `web`은 **external 공유 네트워크**
(`edge`)에 붙고 `db`·`collector`는 RECFlow 전용 내부 네트워크에만 붙는다. 다른 서비스는 `edge`에
합류하고 Caddyfile에 사이트 블록만 추가하면 되며, RECFlow의 DB에는 접근할 수 없다
(계획서 4.2, 22장 18번).

### 8.2 백업

- 매일 02:00 `pg_dump`
- 보관: 일별 7일 / 주별 4주 / 월별 12개월 (계획서 15장)
- 이번 범위에서는 VPS 내부 보관까지 구현하고, 외부 복제(S3/R2/NAS)는 문서에 절차만 남긴다

### 8.3 보안

계획서 16장을 배포 문서의 체크리스트로 옮긴다. 코드로 보장하는 항목은 다음과 같다.

- PostgreSQL 포트를 운영 compose에서 노출하지 않는다
- 모든 비밀값은 `.env`로 관리하고 `.gitignore`에 등록한다
- Caddy가 HTTPS를 강제한다
- 세션 쿠키는 httpOnly · Secure · SameSite=Lax

### 8.4 환경변수

```text
DATABASE_URL=
POSTGRES_DB=
POSTGRES_USER=
POSTGRES_PASSWORD=

KPX_API_KEY=
KPX_DAILY_BUDGET=80

APP_PASSWORD=
AUTH_SECRET=

COLLECTOR_INTERNAL_URL=http://collector:8000
TZ=Asia/Seoul
```

`TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`는 Phase 4에서 추가한다.

### 8.5 운영 모니터링

`/admin` 화면이 `collection_runs`와 collector `GET /health`를 읽어 다음을 표시한다.

```text
REC Collector    정상 / 오류
최근 수집        2026-XX-XX 16:32  (SUCCESS)
최근 실패        없음
누락 의심 거래일 없음
최근 백업        2026-XX-XX 02:00
```

---

## 9. 개발 순서

```text
 1. 리포 초기화, .gitignore, 로컬 docker-compose, PostgreSQL 기동
 2. Prisma 스키마 작성 및 최초 마이그레이션
 3. collector 골격 (models / client / fixture_client / mapping / repository / service) + pytest
 4. fixture 3년치 생성 → backfill 실행 → 적재 및 UPSERT 검증
 5. web 골격: Next.js + Tailwind + shadcn/ui + 로그인 + middleware
 6. lib/analytics TDD (movingAverage · percentile · decisionScore · valuation · simulate)
 7. 대시보드 + 시장분석 화면 + Recharts 차트 + 기간 선택
 8. inventory: 발전소 / 발급 / 매각 CRUD 및 발전소별 집계
 9. simulation: 목표가별 + 분할매각
10. admin: 수집 상태 및 수동 재수집
11. prod compose + Caddy + pg_dump 백업 + 배포 문서
──────────────── API 키 발급 시점에 끼어들어 실행 ────────────────
12. probe 실행 → mapping.py 확정 → 골든 테스트 갱신
13. collector + db 만 먼저 VPS에 배포하여 실데이터 축적 시작
14. 웹 배포 및 백필
```

1~11번은 API 키 없이 완료된다.

**12~13번은 키가 나오는 즉시 다른 작업보다 먼저 실행한다.** REC 데이터는 화·목에만 생성되며
과거 데이터 백필도 일일 예산에 묶여 있으므로, 축적 시작을 웹 완성까지 미루면 그 기간만큼의
데이터를 영구히 잃는다. 수집 시작은 웹 개발과 병행한다.

각 단계 완료 시 `README.md`와 관련 문서를 갱신한다 (계획서 22장).

---

## 10. 계획서에서 변경한 사항 요약

| 항목 | 계획서 | 이 설계 | 이유 |
|---|---|---|---|
| `rec_inventory.status` | `HELD/SOLD/EXPIRED` 컬럼 | 제거, `expired_at`만 유지. 보유량은 파생 계산 | 부분 매각을 표현할 수 없고 `rec_sales`와 이중 기록되어 어긋난다 |
| 스케줄러 | cron 또는 APScheduler | APScheduler (컨테이너 내부) | 호스트 cron 의존 제거, 타임존 고정 |
| 수동 재수집 | 방식 미정 | collector 내부 전용 FastAPI | 웹 관리자 화면에서 실행 가능, 외부 비노출 |
| `price_targets.alert_*` | 포함 | Phase 4로 연기 | 이번 범위에 알림이 없다 |
| `smp_daily`, `alerts` | 스키마 포함 | Phase 4로 연기 | 쓰이지 않는 테이블을 미리 만들지 않는다 |
| 인증 | Auth.js 또는 간단 인증 | 단일 비밀번호 + 서명 쿠키 | 사내 소수 사용자, 사용자 테이블 불필요 |
| 데이터 부족 시 지표 | 명시 없음 | `null` 반환, `—` 표시 | 0으로 채우면 매각 판단 점수가 조용히 틀린다 |

---

## 11. 남은 위험

| 위험 | 영향 | 대응 |
|---|---|---|
| API 응답 필드명 미확정 | 매핑 재작성 | `mapping.py` 한 파일로 격리, 원본 JSON 보존, `probe` 명령 |
| 개발계정 100건/일 | 백필 지연 | 일일 예산 80건, 중단 지점 이어받기. 운영계정 승격 신청을 배포 문서에 안내 |
| 운영계정 심의승인 필요 | 증량 지연 | 개발계정으로도 정기 수집(주 2회)은 충분하다. 백필만 느려진다 |
| 초기 데이터 부족 | MA52·1년 Percentile 계산 불가 | `null` 반환 및 화면 명시. 백필로 완화 |
| 공휴일 휴장 | 누락일 오탐 | `NO_DATA` 마킹으로 재시도 중단 |
