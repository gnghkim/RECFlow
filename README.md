# RECFlow

법인이 보유한 태양광 REC(신재생에너지 공급인증서)의 시장가격을 자동으로 수집·축적하고,
보유량 평가와 매각 시뮬레이션, 설명 가능한 매각 판단 지표를 제공하는 사내 웹 시스템.

REC 현물시장은 매주 화·목요일에만 열린다. 오늘 수집하지 않은 거래일은 나중에 되살릴 수 없으므로,
이 시스템의 첫 번째 책임은 **데이터를 빠짐없이, 중복 없이, 잃지 않고 쌓는 것**이다.

---

## 현재 상태

| 단계 | 범위 | 상태 |
|---|---|---|
| 계획 A | 수집 파이프라인 — 스키마, 수집기, 스케줄러, 백필 | **완료** |
| 계획 B | 웹 — 인증, 대시보드, 시장분석, 보유REC, 시뮬레이션, 관리 | **완료** |
| 계획 C | 배포 — 운영 compose, Caddy, 자동백업 | **완료** |

- 테스트 **180개** 통과 (수집기 68 · 웹 112)
- fixture 기준 3년치(거래일 313일 × 육지/제주/합계 = 939행) 적재 검증 완료
- 공공데이터포털 API 키는 아직 미발급 상태이며, 발급 시 [전환 절차](#api-키가-발급되면)를 따른다

---

## 아키텍처

```text
KPX Open API
     │
     ▼
 collector (Python)
   client → mapping → validation → service → repository
     │                                  │
     │                                  └── 원본 JSON + 실행이력 보존
     ▼
 PostgreSQL
     ▲
     │ (Prisma)
 web (Next.js)  ← 계획 B
     ▲
   Caddy ──▶ 인터넷        ← 계획 C
```

**웹만 외부에 노출된다.** 수집기와 PostgreSQL은 Docker 내부 네트워크에만 존재하며 호스트 포트를
열지 않는다.

### 알아둘 설계 결정

몇 가지는 이유를 모르면 되돌리기 쉬우므로 여기에 적어둔다.

**API 응답 필드명을 아는 파일은 `rec/mapping.py` 하나뿐이다.**
`client`는 HTTP만, `repository`는 SQL만, `service`는 조립 순서만 안다. 세 모듈은 도메인
dataclass로만 대화한다. 공공데이터포털의 응답 필드는 현재 확정되지 않았고, 키 발급 후
`probe` 명령으로 실제 응답을 확인해 이 파일 하나만 고치면 된다. 다른 파일에 필드 문자열을
복사하지 말 것.

**원본은 매핑보다 먼저 저장한다.**
매핑이 실패해도 `rec_market_raw`에 원본이 남으므로 재처리로 복구할 수 있다. API 스펙이
바뀌어 파싱이 깨져도 데이터를 잃지 않는다.

**보유량은 저장하지 않고 계산한다.**
`보유 = 발급(미소멸 합계) − 매각 합계`. 발급 로트를 부분 매각하면 상태 컬럼 하나로 표현할 수
없고, 매각 내역과 이중 기록되어 언젠가 어긋난다.

**값이 없는 것과 0을 구분한다.**
종가와 거래금액은 육지·제주 통합값으로만 제공되므로 육지/제주 행에서는 `NULL`이다. 빈 문자열을
0으로 바꾸면 이후 평균·이동평균·백분위가 조용히 틀어진다.

**스키마는 Prisma가 단독 소유한다.**
Python 수집기는 어떤 DDL도 실행하지 않는다. 테이블 변경은 항상 Prisma 마이그레이션으로만 한다.

**테스트는 `_test`로 끝나는 데이터베이스에서만 돈다.**
테스트 픽스처가 테이블을 비우기 때문에, 대상 데이터베이스 이름을 검사해 아니면 즉시 중단한다.
환경변수 설정을 잊어도 축적된 시세가 지워지지 않는다.

**웹 화면은 전부 동적 렌더링이다.**
Prisma 조회는 Next의 동적 신호가 아니라서 그냥 두면 빌드 시점 값으로 정적 고정되고, 수집이
돌아도 화면 숫자가 갱신되지 않는다. `app/(app)/layout.tsx`의 `force-dynamic` 한 줄이 하위
전체에 적용된다. 지우면 화면이 멀쩡해 보이는 채로 낡은 가격을 보여준다.

**`.env`는 저장소 루트 하나뿐이다.**
Next는 자기 프로젝트 루트에서만 `.env`를 찾으므로 `next.config.ts`가 루트 파일을 명시적으로
읽는다. `apps/web/.env`를 따로 만들지 말 것. 비밀값이 두 곳에 있으면 키 교체 때 한쪽만 바뀐다.

---

## 기술 스택

| 구분 | 사용 기술 |
|---|---|
| 수집기 | Python 3.12, httpx, psycopg 3, APScheduler, FastAPI, pytest |
| 데이터베이스 | PostgreSQL 16 |
| 스키마 | Prisma 6 |
| 웹 | Next.js 16, React 19, TypeScript, Tailwind CSS 4, Recharts 3, jose, decimal.js |
| 실행 | Docker Compose (수집기·DB) / 호스트 Node 24 (웹) |

파이썬은 **컨테이너 안에서만** 실행한다. 호스트에 가상환경을 만들지 않는다.

Next 16은 `middleware.ts`가 아니라 **`proxy.ts`**를 쓰고 Node 런타임에서 돈다. Tailwind 4는
`tailwind.config.js` 없이 CSS의 `@import`와 `@theme`로 설정한다. 둘 다 이전 버전과 다르므로
예전 관행대로 고치지 말 것.

UI 프리미티브는 shadcn CLI 대신 직접 작성했다. 필요한 컴포넌트가 적고, CLI의 대화형 프롬프트가
자동화 환경에서 멈추기 때문이다. API 형태는 shadcn과 맞춰 두어 나중에 교체할 수 있다.

---

## 시작하기

### 1. 기본 구성

```powershell
# Docker Desktop 실행 후
Copy-Item .env.example .env   # 비밀번호를 채운다
docker compose up -d db

npm install
npm run db:migrate
```

### 2. 테스트 데이터베이스 준비 (최초 1회)

```powershell
$exists = docker exec recflow-db psql -U recflow -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = 'recflow_test';"; if ($exists -ne "1") { docker exec recflow-db psql -U recflow -d postgres -c "CREATE DATABASE recflow_test OWNER recflow;" }
$testPassword = (Get-Content .env | Where-Object { $_ -like "POSTGRES_PASSWORD=*" }).Split("=", 2)[1]; $env:DATABASE_URL = "postgresql://recflow:${testPassword}@localhost:5432/recflow_test"; npx prisma migrate deploy --schema prisma/schema.prisma; Remove-Item Env:DATABASE_URL
```

`docker-compose.yml`의 `TEST_DATABASE_URL`은 테스트가 `recflow_test`만 비우도록 지정한다.
`DATABASE_URL`은 수집기 CLI가 개발용 `recflow`에 적재할 때 쓴다.

### 3. 데이터 적재 (API 키 없이)

```powershell
docker compose run --rm collector-test python -m cli gen-fixture --years 3
docker compose run --rm collector-test python -m cli backfill --from 20230812 --to 20260812 --source fixture
```

`--source fixture`는 **HTTP 계층만** 교체한다. 매핑·검증·UPSERT·이력 기록은 실제와 동일한
경로를 지나므로, fixture로 통과한 파이프라인은 키가 생겨도 그대로 동작한다.

### 4. 수집기 상시 구동

```powershell
docker compose up -d collector
```

컨테이너 안에서 APScheduler가 `Asia/Seoul` 기준으로 돈다.

| 시각 | 작업 |
|---|---|
| 화·목 16:30 | 당일 수집 (장 종료 후) |
| 화·목 18:00 | 당일 재확인 |
| 매일 09:00 | 최근 30일 누락일 점검 |

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

### 운영 배포

VPS 배포는 [배포 가이드](docs/deployment.md)를 따른다. 운영은 `docker-compose.prod.yml`을
쓰며 Caddy가 HTTPS를 맡는다. 웹만 외부에 노출되고 DB와 수집기는 내부망에만 있다.

---

## 테스트

```powershell
# 수집기 (컨테이너)
docker compose run --rm collector-test
docker compose run --rm collector-test python -m pytest tests/test_mapping.py -v

# 웹 (호스트)
npm run test
npm run build
```

웹 테스트는 `lib/` 아래 순수 함수만 대상으로 한다. 이동평균·백분위·평가액·시뮬레이션·매각점수가
여기 있고, **데이터가 부족할 때 0이 아니라 `null`을 반환하는 성질**을 이 테스트들이 잠근다.

---

## API 키가 발급되면

공공데이터포털 「한국전력거래소_REC 현물시장 정보」의 응답 필드 영문명은 공개 문서에 없다.
추정하지 않고 실제 응답으로 확정한다.

1. `.env`의 `KPX_API_KEY`에 일반 인증키(Decoding)를 넣는다.
2. 실제 응답을 덤프하고 필드명을 확인한다.

   ```powershell
   docker compose run --rm collector-test python -m cli probe --date <최근 화요일 또는 목요일 YYYYMMDD>
   ```

   원본은 `apps/collector/api-samples/`에 저장되고 실제 필드 목록이 출력된다.

3. 출력에 맞게 `apps/collector/rec/mapping.py`의 `FIELD_MAP`과 `AREA_MAP`을 수정한다.
   **다른 파일은 고칠 필요가 없어야 한다.**
4. `apps/collector/tests/samples/rec_response_sample.json`을 실제 응답으로 교체하고 테스트를 다시 돌린다.
5. fixture 데이터를 지우고 실 데이터로 백필한다.

   ```powershell
   docker exec recflow-db psql -U recflow -d recflow -c "DELETE FROM rec_market WHERE source = 'fixture';"
   docker compose run --rm collector-test python -m cli backfill --from <시작일> --to <종료일> --source api
   ```

개발계정은 **하루 100건**으로 제한되므로 3년치 백필은 며칠에 나뉘어 진행된다. 수집기는 하루
80건에서 스스로 멈추고 다음 실행에서 남은 구간부터 이어받는다.

> 데이터 축적을 웹 완성까지 미루지 말 것. 키가 나오는 즉시 수집기와 DB만 먼저 배포해
> 시세를 쌓기 시작하고, 웹은 병행 개발한다. 미룬 기간만큼의 거래일은 영구히 잃는다.

---

## 명령어

```text
gen-fixture --years N              화·목 시계열 fixture 생성 (재현 가능한 seed)
collect --date YYYYMMDD            거래일 하나 수집
backfill --from ... --to ...       구간 백필 (이미 확정된 날은 건너뜀)
probe --date YYYYMMDD              실 API 원본 응답 덤프 및 필드명 출력
```

모두 `--source api|fixture`를 받는다. 기본값은 `fixture`다.

---

## 저장소 구성

```text
prisma/              DB 스키마 단독 정의 및 마이그레이션
apps/collector/      Python 수집기
  rec/               도메인 모델, 매핑, 클라이언트, 검증, 리포지토리, 서비스
  jobs/              APScheduler 스케줄 등록
  api.py             내부 전용 FastAPI (health, 수동 수집)
  cli.py             명령줄 인터페이스
apps/web/            Next.js 웹 (계획 B)
infra/               Caddy, 백업 스크립트 (계획 C)
docs/
  superpowers/specs/ 설계문서
  superpowers/plans/ 구현계획
```

---

## 문서

- [배포 가이드](docs/deployment.md) — VPS 초기 설정부터 배포·백업·복구까지
- [설계문서](docs/superpowers/specs/2026-08-12-rec-price-tracker-design.md) — 아키텍처, 스키마, 계산 규칙, 변경 사유
- [계획 A — 데이터 파이프라인](docs/superpowers/plans/2026-08-12-plan-a-data-pipeline.md)
- [계획 B — 웹 애플리케이션](docs/superpowers/plans/2026-08-13-plan-b-web-application.md)
