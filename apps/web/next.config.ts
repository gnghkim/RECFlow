import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  output: 'standalone',
  // 계획 C의 Docker 이미지를 위해 리포 루트를 추적 기준으로 삼는다.
  outputFileTracingRoot: process.cwd() + '/../..',
}

export default nextConfig
