import type { NextConfig } from 'next'
import { existsSync } from 'node:fs'
import path from 'node:path'

// 저장소 루트 .env는 Prisma와 collector도 함께 쓰는 단일 진실 원천이다.
const rootEnv = path.resolve(process.cwd(), '../../.env')
if (existsSync(rootEnv)) {
  process.loadEnvFile(rootEnv)
}

const nextConfig: NextConfig = {
  output: 'standalone',
  // 계획 C의 Docker 이미지를 위해 리포 루트를 추적 기준으로 삼는다.
  outputFileTracingRoot: process.cwd() + '/../..',
}

export default nextConfig
