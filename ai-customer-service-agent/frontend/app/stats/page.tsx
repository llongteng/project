"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { fetchStatsOverview, fetchCategoryBreakdown, fetchEscalationReasons, fetchKnowledgeGaps } from "@/lib/api";
import type { StatsOverview, CategoryBreakdown, EscalationReasonItem, KnowledgeGapItem } from "@/lib/types";
import { CATEGORY_LABELS } from "@/lib/constants";

export default function StatsPage() {
  const [overview, setOverview] = useState<StatsOverview | null>(null);
  const [categories, setCategories] = useState<CategoryBreakdown[]>([]);
  const [escalations, setEscalations] = useState<EscalationReasonItem[]>([]);
  const [gaps, setGaps] = useState<KnowledgeGapItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      fetchStatsOverview(),
      fetchCategoryBreakdown(),
      fetchEscalationReasons(),
      fetchKnowledgeGaps(),
    ])
      .then(([o, c, e, g]) => {
        setOverview(o);
        setCategories(c);
        setEscalations(e);
        setGaps(g);
      })
      .catch(() => setError("加载统计数据失败，请确认后端已启动"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-6">
        <p className="text-gray-500 text-center py-12">加载中...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-6">
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {error}
        </div>
        <Link href="/tickets" className="text-blue-600 text-sm mt-3 inline-block">
          ← 返回工单列表
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-4 py-6">
      <Link href="/tickets" className="text-sm text-gray-500 hover:text-gray-700 mb-4 inline-block">
        ← 返回工单列表
      </Link>

      <h1 className="text-xl font-bold text-gray-900 mb-6">运营统计分析</h1>

      {/* Overview Cards */}
      {overview && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
          <StatCard label="总工单数" value={overview.total_tickets} />
          <StatCard label="已解决" value={overview.resolved_tickets} color="text-green-600" />
          <StatCard label="已升级人工" value={overview.escalated_tickets} color="text-red-600" />
          <StatCard label="升级率" value={`${(overview.escalation_rate * 100).toFixed(1)}%`} />
          <StatCard label="知识库命中率" value={`${(overview.kb_hit_rate * 100).toFixed(1)}%`} />
          <StatCard label="平均消息数" value={overview.avg_resolution_messages} />
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Category Breakdown */}
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <h2 className="text-base font-semibold text-gray-900 mb-3">问题分类分布</h2>
          {categories.length > 0 ? (
            <div className="space-y-2">
              {categories.map((c) => (
                <div key={c.category} className="flex items-center justify-between">
                  <span className="text-sm text-gray-700">
                    {CATEGORY_LABELS[c.category] || c.category}
                  </span>
                  <div className="flex items-center gap-2">
                    <div className="w-32 bg-gray-100 rounded-full h-2">
                      <div
                        className="bg-blue-500 rounded-full h-2"
                        style={{
                          width: `${overview ? (c.count / overview.total_tickets) * 100 : 0}%`,
                        }}
                      />
                    </div>
                    <span className="text-xs text-gray-500 w-6 text-right">{c.count}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-400">暂无数据</p>
          )}
        </div>

        {/* Escalation Reasons */}
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <h2 className="text-base font-semibold text-gray-900 mb-3">人工升级原因</h2>
          {escalations.length > 0 ? (
            <div className="space-y-2">
              {escalations.map((e, i) => (
                <div key={i} className="flex items-center justify-between">
                  <span className="text-sm text-gray-700 truncate max-w-[70%]">
                    {e.reason}
                  </span>
                  <span className="text-xs text-gray-500">{e.count} 次</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-400">暂无升级数据（先生成工单总结后查看）</p>
          )}
        </div>

        {/* Knowledge Gaps */}
        <div className="bg-white border border-gray-200 rounded-xl p-5 md:col-span-2">
          <h2 className="text-base font-semibold text-gray-900 mb-3">知识库缺口</h2>
          {gaps.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-gray-400 border-b border-gray-100">
                    <th className="pb-2 font-medium">高频查询</th>
                    <th className="pb-2 font-medium">工单数</th>
                    <th className="pb-2 font-medium">建议分类</th>
                  </tr>
                </thead>
                <tbody>
                  {gaps.map((g, i) => (
                    <tr key={i} className="border-b border-gray-50">
                      <td className="py-2 text-gray-800">{g.search_query}</td>
                      <td className="py-2 text-gray-500">{g.ticket_count}</td>
                      <td className="py-2">
                        <span className="px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-600">
                          {CATEGORY_LABELS[g.suggested_category] || g.suggested_category}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-gray-400">暂无知识库缺口数据（先生成工单总结后查看）</p>
          )}
        </div>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  color = "text-gray-900",
}: {
  label: string;
  value: number | string;
  color?: string;
}) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4">
      <div className="text-xs text-gray-400 mb-1">{label}</div>
      <div className={`text-2xl font-bold ${color}`}>{value}</div>
    </div>
  );
}
