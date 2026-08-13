# syntax=docker/dockerfile:1

# --- 1단계: 의존성 -----------------------------------------------------------
FROM node:24-slim AS deps
WORKDIR /repo

# 루트가 워크스페이스 루트이고 Prisma 도구도 루트에 있다.
COPY package.json package-lock.json ./
COPY apps/web/package.json apps/web/package.json
COPY prisma prisma

# postinstall에서 prisma generate가 돌 수 있도록 스키마를 먼저 복사했다.
RUN npm ci

# --- 2단계: 빌드 -------------------------------------------------------------
FROM node:24-slim AS builder
WORKDIR /repo

COPY --from=deps /repo/node_modules node_modules
COPY package.json package-lock.json ./
COPY prisma prisma
COPY apps/web apps/web

# Prisma 클라이언트를 생성한다. 빌드 시 DB 연결은 필요 없지만
# datasource url 파싱을 위해 형식만 갖춘 값이 있어야 한다.
ENV DATABASE_URL="postgresql://build:build@localhost:5432/build"
RUN npx prisma generate --schema prisma/schema.prisma

ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build --workspace apps/web

# --- 3단계: 실행 -------------------------------------------------------------
FROM node:24-slim AS runner
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0 \
    TZ=Asia/Seoul

# root로 돌리지 않는다.
RUN groupadd --system --gid 1001 nodejs \
 && useradd --system --uid 1001 --gid nodejs nextjs

# standalone 출력에는 필요한 node_modules가 이미 추려져 들어있다.
COPY --from=builder --chown=nextjs:nodejs /repo/apps/web/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /repo/apps/web/.next/static ./apps/web/.next/static

USER nextjs
EXPOSE 3000

CMD ["node", "apps/web/server.js"]
