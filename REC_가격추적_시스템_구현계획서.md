# VPS 기반 태양광 REC 가격추적 시스템 구현계획서

> 목적: 법인이 보유한 태양광 REC의 시장가격을 자동 추적하고, 가격·거래량·SMP·보유 REC를 함께 분석하여 매각 의사결정을 지원하는 내부 웹 시스템 구축

---

## 1. 시스템 목표

### 1.1 핵심 목표
- 한국전력거래소 REC 현물시장 가격 자동 수집
- REC 가격의 장·단기 추세 및 거래량 분석
- SMP 데이터 연계
- 회사 보유 REC 수량 및 취득/발급 현황 관리
- 현재가격 기준 예상 매각금액 계산
- 목표가격별 매각 시뮬레이션
- 목표가격 도달 및 이상변동 알림
- 장기적으로 여러 사내 서비스를 동일 VPS에 추가할 수 있는 구조 확보

### 1.2 시스템 성격
- 외부 공개 서비스가 아닌 회사 내부 업무용
- 실시간 초고빈도 시스템이 아닌 정기 데이터 수집형 시스템
- REC 거래일 데이터를 장기간 축적하여 회사 자체 가격 DB 구축
- 향후 발전량, 매출, 기상정보 등 추가 연계 가능

---

## 2. 권장 기술 스택

| 구분 | 권장 기술 | 용도 |
|---|---|---|
| 서버 | Ubuntu VPS | 전체 서비스 운영 |
| 컨테이너 | Docker + Docker Compose | 서비스 격리 및 배포 |
| Reverse Proxy | Caddy | HTTPS, 서브도메인 |
| Frontend | Next.js + TypeScript | 웹 대시보드 |
| UI | Tailwind CSS + shadcn/ui | 화면 구성 |
| Chart | Recharts | 가격/거래량 차트 |
| Database | PostgreSQL | 시장가격 및 회사 데이터 |
| ORM | Prisma | DB 접근 |
| Collector | Python | REC/SMP API 수집 |
| Scheduler | cron 또는 APScheduler | 정기 수집 |
| Backup | pg_dump + cron | PostgreSQL 자동백업 |
| 인증 | Auth.js 또는 사내 간단 인증 | 사용자 로그인 |
| 알림 | Telegram 우선 | 목표가격 알림 |

---

## 3. 전체 시스템 구조

```text
              ┌───────────────────────────┐
              │ 한국전력거래소 / 공공 API │
              │   REC / SMP / 기타 데이터 │
              └─────────────┬─────────────┘
                            │
                            ▼
                  ┌──────────────────┐
                  │ Python Collector │
                  │ - 정기수집       │
                  │ - 재시도         │
                  │ - 데이터 검증    │
                  └────────┬─────────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │   PostgreSQL     │
                  │                  │
                  │ REC / SMP        │
                  │ 보유 REC         │
                  │ 목표가격         │
                  │ 알림이력         │
                  └────────┬─────────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │ Next.js Web App  │
                  │                  │
                  │ 대시보드         │
                  │ 가격분석         │
                  │ 보유REC 관리     │
                  │ 매각 시뮬레이션  │
                  └────────┬─────────┘
                           │
                  ┌────────┴─────────┐
                  ▼                  ▼
           PC / 모바일          Telegram 알림
```

---

## 4. VPS 구성

### 4.1 권장 VPS 사양

초기 기준:

- CPU: 2 vCPU 이상
- RAM: 4GB 이상
- SSD: 50GB 이상
- OS: Ubuntu LTS
- 고정 IP 권장

REC 시스템 하나만 운영한다면 충분한 수준이다.

향후 WorkWiki, 내부관리시스템 등 여러 서비스를 같이 운영할 경우:

- CPU: 4 vCPU
- RAM: 8GB
- SSD: 100GB 이상

정도로 확장하는 것을 권장한다.

### 4.2 서브도메인 구조 예시

```text
rec.company.co.kr       → REC 가격추적 시스템
wiki.company.co.kr      → WorkWiki
erp.company.co.kr       → 내부 업무 시스템
monitor.company.co.kr   → 서버 모니터링
```

Caddy가 각 서브도메인을 해당 Docker 컨테이너로 연결한다.

---

## 5. Docker 구성

```text
VPS
│
├─ Caddy
│   └─ HTTPS / Reverse Proxy
│
├─ rec-web
│   └─ Next.js
│
├─ rec-collector
│   └─ Python
│
├─ postgres
│   └─ PostgreSQL
│
└─ db-backup
    └─ PostgreSQL Backup
```

### docker-compose 개념

```yaml
services:
  web:
    build: ./apps/web
    restart: unless-stopped
    depends_on:
      - db

  collector:
    build: ./apps/collector
    restart: unless-stopped
    depends_on:
      - db

  db:
    image: postgres
    restart: unless-stopped
    volumes:
      - postgres_data:/var/lib/postgresql/data

  caddy:
    image: caddy
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
```

실제 비밀번호 및 API Key는 코드에 직접 저장하지 않고 `.env`에서 관리한다.

---

## 6. 데이터 수집

### 6.1 REC

기준 데이터:

- 한국전력거래소 REC 현물시장 정보 Open API
- 공공데이터포털 제공

공개 API 기준 주요 데이터:

- 거래일
- 거래건수
- 거래량
- 평균가격
- 종가
- 거래금액
- 육지/제주 구분 데이터

※ 최종 개발 시 실제 API 응답 필드를 기준으로 스키마 매핑

REC 현물시장은 현재 매주 화요일·목요일 10:00~16:00 운영되므로 기본 자동수집은 장 종료 이후 실행한다.

권장 수집 스케줄:

```text
화요일 16:30
목요일 16:30
```

추가 안전수집:

```text
화요일 18:00 재확인
목요일 18:00 재확인
```

같은 거래일 자료가 이미 있으면 UPSERT하여 중복 저장을 방지한다.

### 6.2 SMP

SMP는 별도 한국전력거래소 공개 데이터를 활용한다.

초기 버전에서는:

- 일평균 SMP
- 월평균 SMP
- 육지 기준 SMP

위주로 저장한다.

향후 필요 시 시간별 SMP까지 확장한다.

### 6.3 장애 대응

Collector에는 아래 기능을 기본 적용한다.

- HTTP timeout
- 최대 3회 자동 재시도
- API 오류 로그
- 마지막 정상 수집시간 저장
- 누락 거래일 탐지
- 관리자 수동 재수집
- 중복 데이터 UPSERT

---

## 7. 데이터베이스 설계

### 7.1 `rec_market`

REC 현물시장 가격

```text
id
trade_date
market_area
trade_count
volume
avg_price
high_price
low_price
close_price
trade_amount
source
created_at
updated_at
```

### 7.2 `smp_daily`

```text
id
trade_date
market_area
avg_smp
min_smp
max_smp
created_at
```

### 7.3 `rec_inventory`

회사 보유 REC

```text
id
plant_id
issue_date
rec_quantity
weight
status
memo
created_at
updated_at
```

status 예:

```text
HELD
SOLD
EXPIRED
```

### 7.4 `rec_sales`

실제 REC 매각 내역

```text
id
plant_id
sale_date
quantity
unit_price
sale_amount
buyer
memo
created_at
```

### 7.5 `plants`

발전소 관리

```text
id
name
location
capacity_kw
operation_date
rec_weight
is_active
created_at
```

### 7.6 `price_targets`

목표가격

```text
id
name
target_price
alert_enabled
alert_type
created_at
updated_at
```

예:

```text
1차 매도 검토       75,000원
2차 적극 매도       80,000원
```

### 7.7 `alerts`

```text
id
alert_type
message
trigger_price
sent_at
status
```

---

## 8. 화면 구성

## 8.1 메인 대시보드

첫 화면에서 가장 중요한 정보를 바로 표시한다.

```text
┌────────────────────────────────────────────┐
│ REC MARKET                                │
│ 최근 거래일  2026-08-XX                   │
├─────────┬─────────┬─────────┬──────────────┤
│ 평균가  │ 종가    │ 거래량  │ 전 거래일비 │
│ 71,500  │ 71,600  │ 280,000 │ +1.3%       │
└─────────┴─────────┴─────────┴──────────────┘

REC 가격 추이
─────────────────────────────────────────────
        ╭───────╮
   ╭────╯       ╰─────
───╯

[1개월] [3개월] [6개월] [1년] [3년] [전체]

보유 REC          10,000 REC
현재 평가액        715,000,000원
평균 목표가격      75,000원

매각 판단
가격 위치      ● 높음
추세           ● 상승
거래량         ● 보통
```

---

## 8.2 REC 시장분석

표시 항목:

- 평균가
- 종가
- 최고가
- 최저가
- 거래량
- 거래금액
- 직전 거래일 대비
- 1개월 평균 대비
- 3개월 평균 대비
- 1년 평균 대비

차트:

1. REC 가격
2. 거래량
3. REC + 이동평균
4. 가격 분포

기간 선택:

```text
1M / 3M / 6M / 1Y / 3Y / ALL
```

---

## 8.3 이동평균

REC 현물시장은 주 2회 거래되므로 주식의 일봉 기준과 다르게 해석한다.

초기 적용:

- MA4  : 약 2주
- MA8  : 약 1개월
- MA26 : 약 3개월
- MA52 : 약 6개월
- MA104: 약 1년

대시보드 기본:

```text
현재가격
MA8
MA26
MA52
```

---

## 8.4 가격 위치 분석

단순 미래예측보다 현재 가격이 역사적으로 어디에 위치하는지 보여주는 것을 우선한다.

예:

```text
현재 REC : 73,000원

최근 1개월 평균 : 71,300원
최근 3개월 평균 : 69,800원
최근 1년 평균   : 67,500원

1년 가격 범위
최저 : 61,000원
최고 : 77,500원

현재 Percentile : 87%
```

표시:

```text
0~20%     매우 낮음
20~40%    낮음
40~60%    보통
60~80%    높음
80~100%   매우 높음
```

---

## 8.5 보유 REC 관리

발전소별:

| 발전소 | 발급 REC | 매각 | 보유 | 평가액 |
|---|---:|---:|---:|---:|
| 발전소 A | 5,000 | 2,000 | 3,000 | 자동계산 |
| 발전소 B | 8,000 | 3,000 | 5,000 | 자동계산 |

전체:

```text
총 발급      13,000 REC
총 매각       5,000 REC
현재 보유     8,000 REC
```

---

## 8.6 매각 시뮬레이션

사용자가 원하는 가격을 입력한다.

예:

보유량:

```text
10,000 REC
```

시뮬레이션:

| 가격 | 예상 매출 |
|---:|---:|
| 70,000 | 700,000,000 |
| 72,500 | 725,000,000 |
| 75,000 | 750,000,000 |
| 77,500 | 775,000,000 |
| 80,000 | 800,000,000 |

추가로 현재가격 대비 증가액도 보여준다.

---

## 8.7 분할 매각 시뮬레이션

전량 매각 외에 분할매각도 지원한다.

예:

```text
총 보유량 : 10,000 REC

1차
3,000 REC × 72,000원
= 216,000,000원

2차
3,000 REC × 75,000원
= 225,000,000원

3차
4,000 REC × 78,000원
= 312,000,000원

총 예상매출
753,000,000원

평균 매도가
75,300원
```

---

## 9. 매각 판단 지표

초기에는 AI 가격예측보다 설명 가능한 규칙 기반 점수를 사용한다.

### 예시 점수

#### 가격 위치

```text
1년 Percentile 80% 이상     +2
1년 Percentile 60~80%       +1
40~60%                       0
20~40%                      -1
20% 미만                    -2
```

#### 추세

```text
현재가 > MA8 > MA26          +2
현재가 > MA26                +1
혼조                           0
현재가 < MA26                -1
현재가 < MA8 < MA26          -2
```

#### 거래량

```text
최근 거래량 > 3개월 평균 × 1.2   +1
평균 수준                         0
급감                             -1
```

최종 표시 예:

```text
+4 이상    적극 매도 검토
+2~+3      일부 매도 검토
-1~+1      관망
-2 이하    매도 신중
```

주의:

> 이 지표는 투자 또는 가격예측 모델이 아니라 회사 내부 매각 의사결정 보조지표로 사용한다.

---

## 10. SMP 연계

REC와 SMP를 별도로 보되 한 화면에서도 비교 가능하도록 한다.

```text
REC 가격
SMP
태양광 예상 총수익
```

향후 발전량 데이터까지 입력할 경우:

```text
예상 전력매출
+
예상 REC매출
=
태양광 총 예상매출
```

형태로 발전시킨다.

---

## 11. 알림 시스템

### 11.1 목표가격 알림

예:

```text
REC 평균가격 ≥ 75,000원
```

Telegram:

```text
[REC 가격 알림]

2026-XX-XX REC 현물시장

평균가 : 75,300원
종가   : 75,500원

설정한 목표가격
75,000원을 돌파했습니다.

현재 보유
10,000 REC

현재 예상 매각액
753,000,000원
```

### 11.2 추가 알림

향후:

- 전 거래일 대비 ±5% 이상
- 거래량 급증
- 1년 최고가 갱신
- 목표가격 돌파
- API 데이터 수집 실패
- REC 발급 후 장기간 미매각

---

## 12. API 설계

### 시장 데이터

```text
GET /api/rec/latest
GET /api/rec/history
GET /api/rec/stats
GET /api/rec/chart

GET /api/smp/latest
GET /api/smp/history
```

### 보유 REC

```text
GET    /api/inventory
POST   /api/inventory
PATCH  /api/inventory/:id
DELETE /api/inventory/:id
```

### 매각

```text
GET  /api/sales
POST /api/sales
```

### 매각 시뮬레이션

```text
POST /api/simulation
```

### 목표가격

```text
GET    /api/targets
POST   /api/targets
PATCH  /api/targets/:id
DELETE /api/targets/:id
```

---

## 13. 프로젝트 폴더 구조

```text
rec-monitor/
│
├─ apps/
│   │
│   ├─ web/
│   │   ├─ app/
│   │   │   ├─ dashboard/
│   │   │   ├─ market/
│   │   │   ├─ inventory/
│   │   │   ├─ simulation/
│   │   │   ├─ settings/
│   │   │   └─ api/
│   │   │
│   │   ├─ components/
│   │   ├─ lib/
│   │   └─ package.json
│   │
│   └─ collector/
│       ├─ collectors/
│       │   ├─ rec.py
│       │   └─ smp.py
│       │
│       ├─ jobs/
│       ├─ db/
│       ├─ tests/
│       └─ requirements.txt
│
├─ prisma/
│   └─ schema.prisma
│
├─ infra/
│   ├─ caddy/
│   │   └─ Caddyfile
│   │
│   ├─ backup/
│   └─ scripts/
│
├─ docker-compose.yml
├─ .env.example
├─ README.md
└─ docs/
    └─ architecture.md
```

---

## 14. 환경변수

`.env.example`

```text
DATABASE_URL=

POSTGRES_DB=
POSTGRES_USER=
POSTGRES_PASSWORD=

KPX_API_KEY=

AUTH_SECRET=

TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

실제 `.env`는 Git에 업로드하지 않는다.

---

## 15. 백업 정책

DB 자체 운영에서 가장 중요한 부분이다.

### 자동백업

```text
매일 02:00
PostgreSQL pg_dump
```

보관:

```text
최근 7일    일별
최근 4주    주별
최근 12개월 월별
```

### 권장

VPS 내부에만 백업하지 않고 향후 다음 중 하나로 외부 복제:

- S3 compatible object storage
- Cloudflare R2
- 별도 NAS
- 별도 VPS

---

## 16. 보안

최소 보안 기준:

- SSH Password Login 차단
- SSH Key 로그인
- root 직접 로그인 차단
- UFW Firewall
- 80/443 외 외부 포트 최소화
- PostgreSQL 외부 공개 금지
- HTTPS 강제
- 관리자 로그인 적용
- API Key 환경변수 관리
- Docker 이미지 정기 업데이트
- DB 자동백업

PostgreSQL 포트 `5432`는 인터넷에 공개하지 않는다.

---

## 17. 운영 모니터링

초기에는 복잡한 시스템이 필요하지 않다.

확인 항목:

```text
서버 CPU
RAM
Disk
Docker 상태
DB 상태
최근 REC 수집시간
최근 SMP 수집시간
Collector 오류
Backup 성공 여부
```

관리자 화면에:

```text
REC Collector   정상
SMP Collector   정상
최근 REC 수집   2026-XX-XX 16:32
최근 백업       2026-XX-XX 02:00
```

형태로 표시한다.

---

## 18. 개발 단계

### Phase 1 — MVP

가장 먼저 구현:

- VPS Docker 환경
- PostgreSQL
- REC 데이터 수집
- REC 가격 DB
- 기본 대시보드
- 가격 차트
- 거래량 차트
- 기간별 조회

### Phase 2 — 회사 관리

추가:

- 발전소 관리
- REC 보유량
- 매각내역
- 현재 평가금액
- 목표가격
- 매각 시뮬레이션

### Phase 3 — 의사결정 지원

추가:

- 이동평균
- 1년 Percentile
- 가격 위치
- 거래량 분석
- 매각 판단 점수
- 분할매각 시뮬레이션

### Phase 4 — 자동화

추가:

- Telegram 알림
- 목표가격 알림
- 이상가격 알림
- 데이터 누락 감시
- SMP 데이터 연계

### Phase 5 — 확장

향후:

- 발전량 연계
- 발전소별 월 예상 REC
- 발전소별 수익성
- 기상정보
- 태양광 발전량 예측
- 연간 REC 판매계획
- 실제 매도 실적 대비 분석

---

## 19. 초기 MVP에서 제외할 기능

처음부터 만들 필요가 없는 기능:

- AI 미래가격 예측
- 머신러닝
- 실시간 WebSocket
- 모바일 앱
- 복잡한 권한관리
- 자동 REC 매도
- 과도한 BI 기능

먼저 정확한 데이터 축적이 중요하다.

---

## 20. 핵심 개발 원칙

### 20.1 시장 데이터와 회사 데이터 분리

```text
Market Data
REC / SMP

Company Data
발전소 / 보유REC / 매각내역
```

별도로 관리하여 공개시장 데이터 구조가 변경돼도 회사 데이터에 영향을 최소화한다.

### 20.2 Collector와 Web 분리

```text
Collector → 데이터 생성

Web → 데이터 조회
```

Next.js가 직접 외부 API 수집까지 담당하지 않도록 한다.

### 20.3 원본 데이터 보존

가능하면 API에서 받은 원자료를 별도 JSON 컬럼 또는 raw 테이블에 보관한다.

API 필드 변경이나 계산 오류 발생 시 원자료로 복구할 수 있다.

---

## 21. 추천 최종 구조

```text
                   Internet
                       │
                       ▼
                  Cloudflare
                       │
                       ▼
                    Caddy
                       │
          ┌────────────┴─────────────┐
          │                          │
          ▼                          ▼
    rec.company.co.kr          향후 다른 시스템
          │
          ▼
       Next.js
          │
          ▼
     PostgreSQL
          ▲
          │
    Python Collector
          │
     ┌────┴─────┐
     ▼          ▼
 REC Open API  SMP Data

          │
          ▼
    Telegram Alert
```

---

# 22. 바이브코딩 시작 프롬프트

아래 내용을 Claude Code, Codex 등 개발 에이전트의 초기 프롬프트로 사용할 수 있다.

```text
VPS에서 Docker Compose로 운영하는 내부용 태양광 REC 가격추적
웹 시스템을 구축한다.

기술 스택:

- Ubuntu VPS
- Docker Compose
- Next.js
- TypeScript
- PostgreSQL
- Prisma
- Python Collector
- Tailwind CSS
- shadcn/ui
- Recharts
- Caddy

목표:

1. 한국전력거래소 REC 현물시장 공개 API에서 REC 시장 데이터를 수집한다.
2. Collector는 Next.js와 분리된 Python 서비스로 구현한다.
3. 수집한 데이터는 PostgreSQL에 저장한다.
4. 동일 거래일 데이터는 UPSERT하여 중복을 방지한다.
5. REC 최근가격, 거래량, 평균가, 종가 및 과거 가격 추이를 대시보드에 표시한다.
6. 1개월, 3개월, 6개월, 1년, 3년, 전체 기간 조회를 지원한다.
7. 회사 보유 REC를 관리한다.
8. 현재 REC 가격 기준으로 보유 REC 평가액을 계산한다.
9. 사용자가 목표 매도가를 입력하여 매각금액을 시뮬레이션할 수 있게 한다.
10. 분할매각 시뮬레이션을 지원한다.
11. MA8, MA26, MA52 이동평균을 제공한다.
12. 최근 1년 가격 Percentile을 계산한다.
13. 가격 위치, 추세, 거래량을 조합한 설명 가능한 매각 판단 지표를 제공한다.
14. 목표가격 도달 시 Telegram 알림을 보낼 수 있도록 설계한다.
15. 데이터베이스는 외부 인터넷에 공개하지 않는다.
16. 모든 비밀키는 환경변수로 관리한다.
17. PostgreSQL 자동백업 기능을 포함한다.
18. 다른 내부 웹서비스를 동일 VPS에 추가할 수 있도록 프로젝트와 Docker 구성을 분리한다.

코딩 전 다음 순서로 진행한다.

1. 전체 아키텍처 제안
2. DB schema 설계
3. 폴더 구조 생성
4. docker-compose 작성
5. PostgreSQL/Prisma 구성
6. REC Collector 구현
7. Collector 테스트
8. Next.js API 구현
9. Dashboard 구현
10. Inventory 구현
11. Simulation 구현
12. Alert 구현
13. Backup 구현
14. 배포 문서 작성

각 단계 완료 후 README.md와 관련 문서를 반드시 업데이트한다.

API 응답 필드는 추정하지 말고 실제 공공데이터 API 스펙을 확인한 후 매핑한다.
```

---

# 23. 데이터 출처 참고

- 공공데이터포털: 한국전력거래소_REC 현물시장 정보
  - Base URL 확인 기준: `apis.data.go.kr/B552115/RecMarketInfo2`
- 한국전력거래소: REC 현물시장 / 오늘의 REC
- REC 시장 운영시간 확인 기준: 매주 화·목 10:00~16:00
- SMP 데이터는 한국전력거래소 공개 데이터 중 실제 사용 목적에 맞는 API를 최종 선정하여 연결

> 외부 API의 URL, 필드명 및 제공정책은 변경될 수 있으므로 구현 시점의 공식 API 명세를 최종 기준으로 한다.

---

# 24. 최종 권장 개발 우선순위

**1순위**

```text
REC 자동수집
→ PostgreSQL 축적
→ REC 가격 차트
```

**2순위**

```text
보유 REC
→ 현재 평가액
→ 목표가격별 매각 시뮬레이션
```

**3순위**

```text
가격 위치
→ 이동평균
→ 거래량
→ 매각 판단 지표
```

**4순위**

```text
SMP
→ Telegram
→ 발전량
→ 연간 판매계획
```

이 순서로 개발하면 초기 시스템을 단순하게 유지하면서 실제 시장 데이터를 먼저 축적할 수 있고,
이후 회사의 REC 판매 의사결정 시스템으로 단계적으로 발전시킬 수 있다.
