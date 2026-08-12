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
