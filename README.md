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

### 테스트 DB 준비

테스트는 개발 데이터를 보호하기 위해 이름이 `_test`로 끝나는 전용 데이터베이스에서만 실행된다. 최초 한 번 `recflow_test`를 만들고 같은 Prisma 스키마를 적용한다.

```powershell
$exists = docker exec recflow-db psql -U recflow -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = 'recflow_test';"; if ($exists -ne "1") { docker exec recflow-db psql -U recflow -d postgres -c "CREATE DATABASE recflow_test OWNER recflow;" }
$testPassword = (Get-Content .env | Where-Object { $_ -like "POSTGRES_PASSWORD=*" }).Split("=", 2)[1]; $env:DATABASE_URL = "postgresql://recflow:${testPassword}@localhost:5432/recflow_test"; npx prisma migrate deploy --schema prisma/schema.prisma; Remove-Item Env:DATABASE_URL
```

`docker-compose.yml`의 `TEST_DATABASE_URL`은 테스트 fixture가 `recflow_test`만 비우도록 지정한다. `DATABASE_URL`은 수집기 CLI가 개발용 `recflow`에 백필할 때 사용한다.

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
2. `apps/collector/api-samples`에 실제 응답을 덤프하고 필드명을 확인한다.

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

## 구성

| 디렉토리 | 내용 |
|---|---|
| `prisma/` | DB 스키마 단독 정의 |
| `apps/collector/` | Python 수집기 |
| `apps/web/` | Next.js 웹 (계획 B) |
| `infra/` | Caddy, 백업 스크립트 (계획 C) |
