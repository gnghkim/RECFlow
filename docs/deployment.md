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
