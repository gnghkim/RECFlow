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
