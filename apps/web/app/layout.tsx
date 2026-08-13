import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'RECFlow',
  description: '태양광 REC 가격추적 시스템',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body className="min-h-dvh antialiased">{children}</body>
    </html>
  )
}
