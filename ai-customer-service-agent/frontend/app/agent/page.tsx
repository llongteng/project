"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { batchRunAgent, fetchTickets, runAgentWorkflow, streamAgentReply } from "@/lib/api";
import type { AgentRunResult, TicketListItem, ToolCallData } from "@/lib/types";
import {
  CATEGORY_LABELS,
  PRIORITY_COLORS,
  PRIORITY_LABELS,
  STATUS_COLORS,
  STATUS_LABELS,
} from "@/lib/constants";

export default function AgentPage() {
  const [tickets, setTickets] = useState<TicketListItem[]>([]);
  const [results, setResults] = useState<AgentRunResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [runningId, setRunningId] = useState<number | null>(null);
  const [batchRunning, setBatchRunning] = useState(false);
  const [streamingId, setStreamingId] = useState<number | null>(null);
  const [streamedText, setStreamedText] = useState<Record<number, string>>({});
  const [error, setError] = useState("");

  const loadTickets = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await fetchTickets();
      setTickets(
        data.filter((ticket: TicketListItem) =>
          ["pending", "ai_processing", "waiting_user", "escalated"].includes(ticket.status)
        )
      );
    } catch {
      setError("加载 Agent 队列失败，请确认后端已启动。");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTickets();
  }, [loadTickets]);

  const handleRunOne = async (ticketId: number) => {
    setRunningId(ticketId);
    setError("");
    try {
      const result = await runAgentWorkflow(ticketId);
      setResults((prev) => [result, ...prev.filter((item) => item.ticket_id !== ticketId)]);
      await loadTickets();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Agent 运行失败");
    } finally {
      setRunningId(null);
    }
  };

  const handleStreamOne = async (ticketId: number) => {
    setStreamingId(ticketId);
    setError("");
    setStreamedText((prev) => ({ ...prev, [ticketId]: "" }));

    let toolCalls: ToolCallData[] = [];

    await streamAgentReply(
      ticketId,
      ({ event, data }) => {
        switch (event) {
          case "reply_chunk":
            setStreamedText((prev) => ({
              ...prev,
              [ticketId]: (prev[ticketId] || "") + (data as { content: string }).content,
            }));
            break;
          case "tool_call":
            toolCalls.push(data as ToolCallData);
            break;
          case "done":
            const doneData = data as { reply: string; tool_calls: ToolCallData[]; kb_sources: string[]; need_human: boolean };
            // Add a synthetic result to the sidebar
            setResults((prev) => [
              {
                ticket_id: ticketId,
                status: doneData.need_human ? "escalated" : "waiting_user",
                action: doneData.need_human ? "escalated" : "replied",
                need_human: doneData.need_human,
                kb_hit: doneData.kb_sources.length > 0,
                kb_sources: doneData.kb_sources,
                summary_id: null,
                steps: ["分析问题", "知识库检索", "工具调用", "生成回复"],
                tool_calls: doneData.tool_calls,
              },
              ...prev.filter((item) => item.ticket_id !== ticketId),
            ]);
            loadTickets();
            break;
        }
      },
      (err) => {
        setError(err.message);
      },
      () => {
        setStreamingId(null);
      }
    );
  };

  const handleBatchRun = async () => {
    setBatchRunning(true);
    setError("");
    try {
      const response = await batchRunAgent(5);
      setResults((prev) => [...response.results, ...prev]);
      await loadTickets();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "批量运行失败");
    } finally {
      setBatchRunning(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      <div className="flex items-center justify-between gap-4 mb-6">
        <div>
          <Link href="/tickets" className="text-sm text-gray-500 hover:text-gray-700">
            ← 返回工单列表
          </Link>
          <h1 className="text-2xl font-bold text-gray-900 mt-3">Agent 工作台</h1>
        </div>
        <button
          onClick={handleBatchRun}
          disabled={batchRunning || loading}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          {batchRunning ? "批量处理中..." : "批量处理 5 个待处理工单"}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-4">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6">
        <section className="space-y-3">
          {loading && <p className="text-gray-500 text-center py-12">加载中...</p>}

          {!loading && tickets.length === 0 && (
            <div className="bg-white border border-gray-200 rounded-lg p-8 text-center text-gray-500">
              当前没有需要 Agent 处理的工单。
            </div>
          )}

          {!loading &&
            tickets.map((ticket) => (
              <div key={ticket.id} className="bg-white border border-gray-200 rounded-lg p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm text-gray-400">#{ticket.id}</span>
                      <Link
                        href={`/tickets/${ticket.id}`}
                        className="font-medium text-gray-900 hover:text-blue-700 truncate"
                      >
                        {ticket.title}
                      </Link>
                    </div>
                    <div className="flex flex-wrap items-center gap-2 text-sm text-gray-500">
                      <span>{ticket.customer_name}</span>
                      <span>·</span>
                      <span>{CATEGORY_LABELS[ticket.category] || ticket.category}</span>
                      <span
                        className={`px-2 py-0.5 text-xs rounded-full ${
                          PRIORITY_COLORS[ticket.priority] || ""
                        }`}
                      >
                        {PRIORITY_LABELS[ticket.priority] || ticket.priority}
                      </span>
                      <span
                        className={`px-2 py-0.5 text-xs rounded-full ${
                          STATUS_COLORS[ticket.status] || ""
                        }`}
                      >
                        {STATUS_LABELS[ticket.status] || ticket.status}
                      </span>
                    </div>
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <button
                      onClick={() => handleStreamOne(ticket.id)}
                      disabled={streamingId === ticket.id || runningId === ticket.id || batchRunning}
                      className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50"
                    >
                      {streamingId === ticket.id ? "流式中..." : "流式运行"}
                    </button>
                    <button
                      onClick={() => handleRunOne(ticket.id)}
                      disabled={runningId === ticket.id || streamingId === ticket.id || batchRunning}
                      className="px-3 py-1.5 bg-gray-900 text-white rounded-lg text-sm hover:bg-gray-700 disabled:opacity-50"
                    >
                      {runningId === ticket.id ? "处理中..." : "快速"}
                    </button>
                  </div>
                </div>

                {/* Streaming reply inline */}
                {streamedText[ticket.id] && (
                  <div className="mt-2 p-2 bg-green-50 border border-green-200 rounded text-sm text-gray-700">
                    {streamedText[ticket.id]}
                    {streamingId === ticket.id && (
                      <span className="inline-block w-2 h-4 bg-blue-500 animate-pulse ml-0.5 align-middle" />
                    )}
                  </div>
                )}
              </div>
            ))}
        </section>

        <aside className="bg-white border border-gray-200 rounded-lg p-4 h-fit">
          <h2 className="text-base font-semibold text-gray-900 mb-3">最近运行结果</h2>
          {results.length === 0 ? (
            <p className="text-sm text-gray-400">暂无运行记录</p>
          ) : (
            <div className="space-y-3">
              {results.slice(0, 8).map((result, index) => (
                <div key={`${result.ticket_id}-${index}`} className="border-b border-gray-100 pb-3 last:border-0">
                  <div className="flex items-center justify-between">
                    <Link
                      href={`/tickets/${result.ticket_id}`}
                      className="text-sm font-medium text-gray-900 hover:text-blue-700"
                    >
                      工单 #{result.ticket_id}
                    </Link>
                    <span
                      className={`px-2 py-0.5 text-xs rounded-full ${
                        STATUS_COLORS[result.status] || "bg-gray-100 text-gray-600"
                      }`}
                    >
                      {STATUS_LABELS[result.status] || result.status}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 mt-1">
                    {result.kb_hit ? `引用: ${result.kb_sources.join("、")}` : "未命中知识库，已升级人工"}
                  </p>
                  {result.tool_calls && result.tool_calls.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {result.tool_calls.map((tc, i) => (
                        <span key={i} className="px-1.5 py-0.5 bg-yellow-50 text-yellow-700 border border-yellow-200 rounded text-xs">
                          {tc.tool}
                        </span>
                      ))}
                    </div>
                  )}
                  <div className="flex flex-wrap gap-1 mt-2">
                    {result.steps.map((step) => (
                      <span key={step} className="px-1.5 py-0.5 bg-gray-100 text-gray-500 rounded text-xs">
                        {step}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
