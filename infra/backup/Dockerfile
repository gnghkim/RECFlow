# db 와 같은 major 를 써야 pg_dump 가 호환된다.
FROM postgres:16-alpine

ENV TZ=Asia/Seoul

# alpine 의 date 는 -d 옵션을 제한적으로 지원하므로 coreutils 를 넣는다.
RUN apk add --no-cache coreutils tzdata

COPY backup.sh /usr/local/bin/backup.sh
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/backup.sh /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
