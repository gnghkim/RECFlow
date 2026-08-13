#!/bin/sh
# 로그인 비밀번호를 바꾼다. 저장소 루트에서 실행한다.
#
#   ./infra/scripts/change-password.sh                 새 비밀번호 자동 생성
#   ./infra/scripts/change-password.sh --set '원하는값'  직접 지정
#   ./infra/scripts/change-password.sh --with-secret    세션 서명키까지 교체
#
# --with-secret 은 AUTH_SECRET 을 함께 바꿔 **접속 중인 모든 사용자를 즉시
# 로그아웃**시킨다. 비밀번호만 바꾸면 기존 세션 쿠키는 최대 12시간 유효하다.
# 유출이 의심되면 반드시 --with-secret 을 쓴다.
#
# 주의: 이 시스템은 비밀번호 하나를 여러 사람이 공유한다. 바꾸면 나머지
# 사용자도 전부 다시 로그인해야 하므로 미리 알리고 바꾼다.
set -eu

COMPOSE_FILE=docker-compose.prod.yml
ENV_FILE=.env

NEW_PASSWORD=""
ROTATE_SECRET=0

while [ $# -gt 0 ]; do
  case "$1" in
    --set)
      shift
      [ $# -gt 0 ] || { echo "오류: --set 뒤에 값이 필요하다" >&2; exit 1; }
      NEW_PASSWORD="$1"
      ;;
    --with-secret) ROTATE_SECRET=1 ;;
    -h|--help)
      # 파일 상단 주석 블록만 출력한다. set -eu 를 만나면 멈춘다.
      sed -n '2,/^set -eu/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "알 수 없는 옵션: $1" >&2; exit 1 ;;
  esac
  shift
done

[ -f "$ENV_FILE" ] || { echo "오류: $ENV_FILE 이 없다. 저장소 루트에서 실행하라." >&2; exit 1; }
[ -f "$COMPOSE_FILE" ] || { echo "오류: $COMPOSE_FILE 이 없다. 저장소 루트에서 실행하라." >&2; exit 1; }

if [ -z "$NEW_PASSWORD" ]; then
  NEW_PASSWORD=$(openssl rand -base64 18 | tr -d '/+=' | cut -c1-20)
fi

# 비밀번호에 sed 구분자나 개행이 들어가면 .env 가 깨진다.
case "$NEW_PASSWORD" in
  *"|"*|*"
"*) echo "오류: 비밀번호에 | 또는 개행을 쓸 수 없다" >&2; exit 1 ;;
esac
[ ${#NEW_PASSWORD} -ge 8 ] || { echo "오류: 비밀번호는 8자 이상이어야 한다" >&2; exit 1; }

# 되돌릴 수 있게 먼저 백업한다.
BACKUP="${ENV_FILE}.bak.$(date +%Y%m%d-%H%M%S)"
cp "$ENV_FILE" "$BACKUP"
chmod 600 "$BACKUP"

sed -i "s|^APP_PASSWORD=.*|APP_PASSWORD=${NEW_PASSWORD}|" "$ENV_FILE"

if [ "$ROTATE_SECRET" = "1" ]; then
  NEW_SECRET=$(openssl rand -base64 48 | tr -d '\n')
  sed -i "s|^AUTH_SECRET=.*|AUTH_SECRET=${NEW_SECRET}|" "$ENV_FILE"
fi

# 웹만 다시 만든다. 수집기와 DB는 건드리지 않으므로 수집이 끊기지 않는다.
docker compose -f "$COMPOSE_FILE" up -d web >/dev/null

echo "완료."
echo
echo "  새 비밀번호: ${NEW_PASSWORD}"
if [ "$ROTATE_SECRET" = "1" ]; then
  echo "  AUTH_SECRET 교체됨 -> 접속 중이던 사용자가 전부 로그아웃되었다"
else
  echo "  기존 세션은 최대 12시간 유효하다. 즉시 끊으려면 --with-secret 으로 다시 실행한다"
fi
echo "  이전 설정 백업: ${BACKUP}"
echo
echo "확인:"
echo "  curl -s -X POST https://\$(grep '^RECFLOW_DOMAIN=' $ENV_FILE | cut -d= -f2)/api/auth/login \\"
echo "    -H 'content-type: application/json' -d '{\"password\":\"${NEW_PASSWORD}\"}'"
echo
echo "로그인 시도는 IP당 분당 5회로 제한된다. 확인 중 429가 나오면 1분 기다린다."
