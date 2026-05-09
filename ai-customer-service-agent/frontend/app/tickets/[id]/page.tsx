"use client";

import { useCallback, useEffect, useState, use } from "react";
import Link from "next/link";
import { fetchTicket, updateTicketStatus, addMessage, analyzeTicket, autoReply, generateSummary, fetchTicketSummary, runAgentWorkflow, streamAgentReply } from "@/lib/api";
import { AgentRunResult, TicketDetail, TicketSummary, ToolCallData } from "@/lib/types";
import {
  STATUS_LABELS,
  STATUS_COLORS,
  PRIORITY_LABELS,
  PRIORITY_COLORS,
  CATEGORY_LABELS,
  SENTIMENT_LABELS,
  SENTIMENT_COLORS,
} from "@/lib/constants";

const STATUS_FLOW: Record<string, string[]> = {
  pending: ["ai_processing", "escalated", "resolved"],
  ai_processing: ["waiting_user", "escalated", "resolved"],
  waiting_user: ["ai_processing", "escalated", "resolved"],
  resolved: [],
  escalated: ["pending", "ai_processing", "resolved"],
};

const ROLE_LABELS: Record<string, string> = {
  user: "用户",
  agent: "客服",
  system: "系统",
};

const ROLE_COLORS: Record<string, string> = {
  user: "bg-blue-50 border-blue-200",
  agent: "bg-green-50 border-green-200",
  system: "bg-gray-50 border-gray-200",
};

export default function TicketDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const ticketId = parseInt(id);
  const [ticket, setTicket] = useState<TicketDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [replyText, setReplyText] = useState("");
  const [sending, setSending] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [autoReplying, setAutoReplying] = useState(false);
  const [summary, setSummary] = useState<TicketSummary | null>(null);
  const [summarizing, setSummarizing] = useState(false);
  const [agentRunning, setAgentRunning] = useState(false);
  const [agentResult, setAgentResult] = useState<AgentRunResult | null>(null);

  // Streaming state
  const [streaming, setStreaming] = useState(false);
  const [streamState, setStreamState] = useState<"idle" | "analyzing" | "searching" | "replying" | "done">("idle");
  const [streamedReply, setStreamedReply] = useState("");
  const [streamToolCalls, setStreamToolCalls] = useState<ToolCallData[]>([]);
  const [streamKbSources, setStreamKbSources] = useState<string[]>([]);
  const [expandedTools, setExpandedTools] = useState<Set<number>>(new Set());

  const loadTicket = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await fetchTicket(ticketId);
      setTicket(data);
    } catch {
      setError("工单不存在或加载失败");
    } finally {
      setLoading(false);
    }
  }, [ticketId]);

  useEffect(() => {
    loadTicket();
  }, [loadTicket]);

  useEffect(() => {
    fetchTicketSummary(ticketId).then(setSummary).catch(() => {});
  }, [ticketId]);

  const handleGenerateSummary = async () => {
    setSummarizing(true);
    try {
      const s = await generateSummary(ticketId);
      setSummary(s);
    } catch {
      alert("生成总结失败");
    } finally {
      setSummarizing(false);
    }
  };

  const handleStatusChange = async (newStatus: string) => {
    try {
      const updated = await updateTicketStatus(ticketId, newStatus);
      setTicket(updated);
    } catch {
      alert("状态更新失败");
    }
  };

  const handleAnalyze = async () => {
    setAnalyzing(true);
    try {
      await analyzeTicket(ticketId);
      await loadTicket();
    } catch {
      alert("分析失败，请确认后端已启动");
    } finally {
      setAnalyzing(false);
    }
  };

  const handleAutoReply = async () => {
    setAutoReplying(true);
    try {
      const updatedTicket = await autoReply(ticketId);
      setTicket(updatedTicket);
    } catch {
      alert("自动回复生成失败");
    } finally {
      setAutoReplying(false);
    }
  };

  const handleRunAgent = async () => {
    setAgentRunning(true);
    try {
      const result = await runAgentWorkflow(ticketId);
      setAgentResult(result);
      await loadTicket();
      const s = await fetchTicketSummary(ticketId);
      setSummary(s);
    } catch {
      alert("Agent 工作流运行失败");
    } finally {
      setAgentRunning(false);
    }
  };

  const handleStreamReply = async () => {
    setStreaming(true);
    setStreamState("analyzing");
    setStreamedReply("");
    setStreamToolCalls([]);
    setStreamKbSources([]);
    setExpandedTools(new Set());

    await streamAgentReply(
      ticketId,
      ({ event, data }) => {
        switch (event) {
          case "analysis_start":
            setStreamState("analyzing");
            break;
          case "analysis_done":
            setStreamState("searching");
            break;
          case "kb_search_done":
            setStreamKbSources((data as { sources: string[] }).sources || []);
            setStreamState("replying");
            break;
          case "reply_chunk":
            setStreamedReply((prev) => prev + (data as { content: string }).content);
            break;
          case "tool_call":
            setStreamToolCalls((prev) => [...prev, data as ToolCallData]);
            break;
          case "done":
            setStreamState("done");
            loadTicket();
            break;
        }
      },
      (err) => {
        setStreamState("done");
        alert("流式回复失败: " + err.message);
      },
      () => {
        setStreaming(false);
      }
    );
  };

  const handleSendReply = async () => {
    if (!replyText.trim()) return;
    setSending(true);
    try {
      await addMessage(ticketId, { role: "agent", content: replyText.trim() });
      setReplyText("");
      await loadTicket();
    } catch {
      alert("发送失败");
    } finally {
      setSending(false);
    }
  };

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-6">
        <p className="text-gray-500 text-center py-12">加载中...</p>
      </div>
    );
  }

  if (error || !ticket) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-6">
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {error || "工单不存在"}
        </div>
        <Link href="/tickets" className="text-blue-600 text-sm mt-3 inline-block">
          ← 返回列表
        </Link>
      </div>
    );
  }

  const availableStatuses = STATUS_FLOW[ticket.status] || [];
  const hasAnalysis = ticket.analysis_status === "completed";

  return (
    <div className="max-w-4xl mx-auto px-4 py-6">
      <Link
        href="/tickets"
        className="text-sm text-gray-500 hover:text-gray-700 mb-4 inline-block"
      >
        ← 返回列表
      </Link>

      {/* Ticket header */}
      <div className="bg-white border border-gray-200 rounded-xl p-6 mb-6">
        <div className="flex items-start justify-between gap-4 mb-4">
          <div>
            <h1 className="text-xl font-bold text-gray-900 mb-1">
              #{ticket.id} {ticket.title}
            </h1>
            <div className="text-sm text-gray-500 space-x-2">
              <span>{ticket.customer_name}</span>
              <span>·</span>
              <span>{ticket.customer_email}</span>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
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

        <div className="flex items-center gap-2 text-sm text-gray-500 mb-3">
          <span>分类: {CATEGORY_LABELS[ticket.category] || ticket.category}</span>
          <span>·</span>
          <span>创建: {new Date(ticket.created_at).toLocaleString("zh-CN")}</span>
        </div>

        {/* Status actions */}
        {availableStatuses.length > 0 && (
          <div className="flex items-center gap-2 pt-3 border-t border-gray-100">
            <span className="text-xs text-gray-400">变更状态:</span>
            {availableStatuses.map((s) => (
              <button
                key={s}
                onClick={() => handleStatusChange(s)}
                className="px-3 py-1 text-xs rounded-full border border-gray-200 hover:bg-gray-100 text-gray-700"
              >
                {STATUS_LABELS[s]}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* AI Analysis Panel */}
      <div className="bg-white border border-gray-200 rounded-xl p-6 mb-6">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-gray-900">AI 分析结果</h2>
          <button
            onClick={handleAnalyze}
            disabled={analyzing}
            className="px-3 py-1 text-xs text-blue-600 border border-blue-200 rounded-full hover:bg-blue-50 disabled:opacity-50"
          >
            {analyzing ? "分析中..." : "重新分析"}
          </button>
        </div>

        {hasAnalysis ? (
          <div className="space-y-3">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div>
                <span className="text-xs text-gray-400">情绪</span>
                <div>
                  <span
                    className={`inline-block mt-1 px-2 py-0.5 text-xs rounded-full ${
                      SENTIMENT_COLORS[ticket.sentiment || ""] || "bg-gray-100 text-gray-600"
                    }`}
                  >
                    {SENTIMENT_LABELS[ticket.sentiment || ""] || ticket.sentiment || "-"}
                  </span>
                </div>
              </div>
              <div>
                <span className="text-xs text-gray-400">AI 分类</span>
                <div className="mt-1 text-sm font-medium text-gray-900">
                  {CATEGORY_LABELS[ticket.ai_category || ""] || ticket.ai_category || "-"}
                </div>
              </div>
              <div>
                <span className="text-xs text-gray-400">AI 优先级</span>
                <div>
                  <span
                    className={`inline-block mt-1 px-2 py-0.5 text-xs rounded-full ${
                      PRIORITY_COLORS[ticket.ai_priority || ""] || ""
                    }`}
                  >
                    {PRIORITY_LABELS[ticket.ai_priority || ""] || ticket.ai_priority || "-"}
                  </span>
                </div>
              </div>
              <div>
                <span className="text-xs text-gray-400">人工介入</span>
                <div>
                  <span
                    className={`inline-block mt-1 px-2 py-0.5 text-xs rounded-full ${
                      ticket.need_human
                        ? "bg-red-100 text-red-700"
                        : "bg-gray-100 text-gray-600"
                    }`}
                  >
                    {ticket.need_human ? "需要" : "不需要"}
                  </span>
                </div>
              </div>
            </div>
            {ticket.analysis_reason && (
              <div className="pt-3 border-t border-gray-100">
                <span className="text-xs text-gray-400">分析理由</span>
                <p className="mt-1 text-sm text-gray-700">{ticket.analysis_reason}</p>
              </div>
            )}
            <div className="text-xs text-gray-400">
              分析时间:{" "}
              {ticket.analyzed_at
                ? new Date(ticket.analyzed_at).toLocaleString("zh-CN")
                : "-"}
            </div>
          </div>
        ) : (
          <div className="text-center py-6">
            <p className="text-sm text-gray-400">
              {ticket.analysis_status === "failed"
                ? "分析失败，请点击重新分析"
                : "尚未分析，系统会在创建工单时自动分析，或点击上方按钮手动触发"}
            </p>
          </div>
        )}
      </div>

      {/* Ticket Summary Panel */}
      <div className="bg-white border border-gray-200 rounded-xl p-6 mb-6">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-gray-900">工单总结</h2>
          <button
            onClick={handleGenerateSummary}
            disabled={summarizing}
            className="px-3 py-1 text-xs text-indigo-600 border border-indigo-200 rounded-full hover:bg-indigo-50 disabled:opacity-50"
          >
            {summarizing ? "生成中..." : summary ? "重新生成总结" : "生成总结"}
          </button>
        </div>

        {summary ? (
          <div className="space-y-3">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div>
                <span className="text-xs text-gray-400">问题类型</span>
                <div className="mt-1 text-sm font-medium text-gray-900">
                  {CATEGORY_LABELS[summary.category] || summary.category}
                </div>
              </div>
              <div>
                <span className="text-xs text-gray-400">用户情绪</span>
                <div className="mt-1 text-sm font-medium text-gray-900">
                  {SENTIMENT_LABELS[summary.sentiment] || summary.sentiment}
                </div>
              </div>
              <div>
                <span className="text-xs text-gray-400">知识库</span>
                <div className="mt-1">
                  <span className={`inline-block px-2 py-0.5 text-xs rounded-full ${
                    summary.knowledge_used
                      ? "bg-green-100 text-green-700"
                      : "bg-gray-100 text-gray-600"
                  }`}>
                    {summary.knowledge_used ? "已使用" : "未使用"}
                  </span>
                </div>
              </div>
              <div>
                <span className="text-xs text-gray-400">人工介入</span>
                <div className="mt-1">
                  <span className={`inline-block px-2 py-0.5 text-xs rounded-full ${
                    summary.need_human
                      ? "bg-red-100 text-red-700"
                      : "bg-gray-100 text-gray-600"
                  }`}>
                    {summary.need_human ? "需要" : "不需要"}
                  </span>
                </div>
              </div>
            </div>
            {summary.escalation_reason && (
              <div>
                <span className="text-xs text-gray-400">升级原因</span>
                <p className="mt-1 text-sm text-gray-700">{summary.escalation_reason}</p>
              </div>
            )}
            <div className="pt-3 border-t border-gray-100">
              <span className="text-xs text-gray-400">完整总结</span>
              <pre className="mt-1 text-sm text-gray-700 whitespace-pre-wrap font-sans bg-gray-50 rounded-lg p-3">
                {summary.summary_text}
              </pre>
            </div>
            <div className="text-xs text-gray-400">
              生成时间: {new Date(summary.created_at).toLocaleString("zh-CN")}
            </div>
          </div>
        ) : (
          <div className="text-center py-4">
            <p className="text-sm text-gray-400">尚未生成总结，点击上方按钮生成</p>
          </div>
        )}
      </div>

      {/* Agent Workflow Panel */}
      <div className="bg-white border border-gray-200 rounded-xl p-6 mb-6">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-gray-900">Agent 工作流</h2>
          <div className="flex gap-2">
            <button
              onClick={handleStreamReply}
              disabled={streaming || ticket.status === "resolved"}
              className="px-3 py-1 text-xs bg-blue-600 text-white rounded-full hover:bg-blue-700 disabled:opacity-50"
            >
              {streaming ? "处理中..." : "流式处理"}
            </button>
            <button
              onClick={handleRunAgent}
              disabled={agentRunning || streaming || ticket.status === "resolved"}
              className="px-3 py-1 text-xs text-gray-900 border border-gray-300 rounded-full hover:bg-gray-50 disabled:opacity-50"
            >
              {agentRunning ? "运行中..." : "快速流程"}
            </button>
          </div>
        </div>

        {/* Streaming progress */}
        {(streaming || streamState !== "idle") && (
          <div className="space-y-3">
            {/* Step indicator */}
            <div className="flex items-center gap-3">
              {["analyzing", "searching", "replying"].map((step, i) => {
                const stepLabels = ["分析中", "检索中", "回复中"];
                const isActive = streamState === step;
                const isDone =
                  (step === "analyzing" && ["searching", "replying", "done"].includes(streamState)) ||
                  (step === "searching" && ["replying", "done"].includes(streamState)) ||
                  (step === "replying" && streamState === "done");
                return (
                  <div key={step} className="flex items-center gap-1">
                    <span
                      className={`inline-flex items-center justify-center w-5 h-5 rounded-full text-xs font-bold ${
                        isDone
                          ? "bg-green-100 text-green-700"
                          : isActive
                          ? "bg-blue-100 text-blue-700 animate-pulse"
                          : "bg-gray-100 text-gray-400"
                      }`}
                    >
                      {isDone ? "✓" : i + 1}
                    </span>
                    <span className={`text-xs ${isDone ? "text-green-600" : isActive ? "text-blue-600" : "text-gray-400"}`}>
                      {stepLabels[i]}
                    </span>
                  </div>
                );
              })}
            </div>

            {/* Tool call cards */}
            {streamToolCalls.length > 0 && (
              <div className="space-y-2">
                <span className="text-xs text-gray-400 font-medium">工具调用</span>
                {streamToolCalls.map((tc, idx) => (
                  <div key={idx} className="border border-gray-200 rounded-lg overflow-hidden">
                    <button
                      onClick={() => {
                        const next = new Set(expandedTools);
                        expandedTools.has(idx) ? next.delete(idx) : next.add(idx);
                        setExpandedTools(next);
                      }}
                      className="w-full flex items-center justify-between px-3 py-2 text-xs bg-gray-50 hover:bg-gray-100"
                    >
                      <span className="font-medium text-gray-700">
                        🔧 {tc.tool}
                      </span>
                      <span className="text-gray-400">{expandedTools.has(idx) ? "▲" : "▼"}</span>
                    </button>
                    {expandedTools.has(idx) && (
                      <div className="px-3 py-2 space-y-1 text-xs">
                        <div>
                          <span className="text-gray-400">Input: </span>
                          <code className="text-gray-700">{JSON.stringify(tc.input)}</code>
                        </div>
                        <div>
                          <span className="text-gray-400">Output: </span>
                          <code className="text-gray-700">{JSON.stringify(tc.output)}</code>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Streaming reply */}
            {streamedReply && (
              <div className="border border-green-200 bg-green-50 rounded-lg p-3">
                <span className="text-xs text-green-600 font-medium block mb-1">AI 回复</span>
                <p className="text-sm text-gray-800 whitespace-pre-wrap">
                  {streamedReply}
                  {streamState === "replying" && (
                    <span className="inline-block w-2 h-4 bg-blue-500 animate-pulse ml-0.5 align-middle" />
                  )}
                </p>
              </div>
            )}

            {/* KB sources */}
            {streamKbSources.length > 0 && (
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-400">引用知识库:</span>
                {streamKbSources.map((s) => (
                  <span key={s} className="px-2 py-0.5 bg-green-100 text-green-700 rounded-full text-xs">
                    {s}
                  </span>
                ))}
              </div>
            )}

            {streamState === "done" && (
              <p className="text-xs text-green-600">流式处理完成</p>
            )}
          </div>
        )}

        {/* Show previous agent result if exists and not streaming */}
        {!streaming && streamState === "idle" && agentResult && (
          <div className="space-y-2 mt-3">
            <div className="flex flex-wrap gap-2">
              {agentResult.steps.map((step) => (
                <span key={step} className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded-full text-xs">
                  {step}
                </span>
              ))}
            </div>
            {agentResult.tool_calls && agentResult.tool_calls.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {agentResult.tool_calls.map((tc, i) => (
                  <span key={i} className="px-2 py-0.5 bg-yellow-50 text-yellow-700 border border-yellow-200 rounded-full text-xs">
                    已调: {tc.tool}
                  </span>
                ))}
              </div>
            )}
            <p className="text-sm text-gray-600">
              {agentResult.kb_hit
                ? `已引用知识库：${agentResult.kb_sources.join("、")}`
                : "未命中知识库，已升级人工处理。"}
            </p>
          </div>
        )}

        {!streaming && streamState === "idle" && !agentResult && (
          <p className="text-sm text-gray-400">
            点击「流式处理」实时查看 Agent 分析、检索、工具调用和回复生成过程。
          </p>
        )}
      </div>

      {/* Message flow */}
      <h2 className="text-lg font-semibold text-gray-900 mb-3">消息记录</h2>
      <div className="space-y-3 mb-6">
        {ticket.messages.map((msg) => (
          <div
            key={msg.id}
            className={`border rounded-lg px-4 py-3 ${ROLE_COLORS[msg.role] || "bg-gray-50 border-gray-200"}`}
          >
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-medium text-gray-500">
                {ROLE_LABELS[msg.role] || msg.role}
              </span>
              <span className="text-xs text-gray-400">
                {new Date(msg.created_at).toLocaleString("zh-CN")}
              </span>
            </div>
            <p className="text-sm text-gray-800 whitespace-pre-wrap">
              {msg.content}
            </p>
          </div>
        ))}
        {ticket.messages.length === 0 && (
          <p className="text-gray-400 text-sm text-center py-6">暂无消息</p>
        )}
      </div>

      {/* Reply box */}
      <div className="bg-white border border-gray-200 rounded-xl p-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-medium text-gray-700">发送客服回复</h3>
          <button
            onClick={handleAutoReply}
            disabled={autoReplying}
            className="px-3 py-1 text-xs text-purple-600 border border-purple-200 rounded-full hover:bg-purple-50 disabled:opacity-50"
          >
            {autoReplying ? "生成中..." : "AI 自动回复"}
          </button>
        </div>

        <textarea
          value={replyText}
          onChange={(e) => setReplyText(e.target.value)}
          rows={3}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mb-2"
          placeholder="输入回复内容..."
        />
        <div className="flex justify-end">
          <button
            onClick={handleSendReply}
            disabled={sending || !replyText.trim()}
            className="px-4 py-2 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
          >
            {sending ? "发送中..." : "发送回复"}
          </button>
        </div>
      </div>
    </div>
  );
}
