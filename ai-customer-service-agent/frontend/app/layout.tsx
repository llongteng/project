import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI 客服工单系统",
  description: "AI Customer Service Ticket System",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" className="h-full antialiased">
      <body className="min-h-full flex flex-col bg-gray-50">
        <nav className="bg-white border-b border-gray-200 px-6 py-3">
          <div className="max-w-6xl mx-auto flex items-center justify-between">
            <Link href="/tickets" className="text-lg font-bold text-gray-900">
              AI 客服工单系统
            </Link>
            <div className="flex items-center gap-4">
              <Link
                href="/tickets"
                className="text-sm text-gray-600 hover:text-gray-900"
              >
                工单列表
              </Link>
              <Link
                href="/knowledge"
                className="text-sm text-gray-600 hover:text-gray-900"
              >
                知识库
              </Link>
              <Link
                href="/analytics"
                className="text-sm text-gray-600 hover:text-gray-900"
              >
                数据分析
              </Link>
              <Link
                href="/agent"
                className="text-sm text-gray-600 hover:text-gray-900"
              >
                Agent 工作台
              </Link>
            </div>
          </div>
        </nav>
        <main className="flex-1">{children}</main>
      </body>
    </html>
  );
}
