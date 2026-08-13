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
