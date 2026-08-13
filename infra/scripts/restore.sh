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
