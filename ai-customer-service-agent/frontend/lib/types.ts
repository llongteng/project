export interface TicketListItem {
  id: number;
  title: string;
  customer_name: string;
  category: string;
  priority: string;
  status: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  sentiment: string | null;
  ai_category: string | null;
  ai_priority: string | null;
  need_human: boolean;
}

export interface MessageItem {
  id: number;
  ticket_id: number;
  role: "user" | "agent" | "system";
  content: string;
  created_at: string;
}

export interface AnalysisResult {
  sentiment: string;
  ai_category: string;
  ai_priority: string;
  need_human: boolean;
  analysis_reason: string;
  analysis_status: string;
  analyzed_at: string | null;
}

export interface KBEntry {
  id: number;
  title: string;
  category: string;
  content: string;
  keywords: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface TicketDetail {
  id: number;
  title: string;
  customer_name: string;
  customer_email: string;
  category: string;
  priority: string;
  status: string;
  created_at: string;
  updated_at: string;
  messages: MessageItem[];
  sentiment: string | null;
  ai_category: string | null;
  ai_priority: string | null;
  need_human: boolean;
  analysis_reason: string | null;
  analysis_status: string | null;
  analyzed_at: string | null;
}

export interface TicketSummary {
  id: number;
  ticket_id: number;
  problem: string;
  category: string;
  sentiment: string;
  resolution: string;
  final_status: string;
  need_human: boolean;
  escalation_reason: string;
  knowledge_used: boolean;
  summary_text: string;
  created_at: string;
  updated_at: string;
}

export interface StatsOverview {
  total_tickets: number;
  resolved_tickets: number;
  escalated_tickets: number;
  escalation_rate: number;
  kb_hit_rate: number;
  avg_resolution_messages: number;
}

export interface CategoryBreakdown {
  category: string;
  count: number;
}

export interface EscalationReasonItem {
  reason: string;
  count: number;
}

export interface KnowledgeGapItem {
  search_query: string;
  ticket_count: number;
  suggested_category: string;
}

export interface FrequentIssues {
  keywords: string[];
  categories: CategoryBreakdown[];
  suggested_kb_gaps: KnowledgeGapItem[];
}

export interface AgentRunResult {
  ticket_id: number;
  status: string;
  action: string;
  need_human: boolean;
  kb_hit: boolean;
  kb_sources: string[];
  summary_id: number | null;
  steps: string[];
  tool_calls: ToolCallRecord[];
}

export interface ToolCallRecord {
  tool: string;
  input: Record<string, unknown>;
  output: Record<string, unknown>;
}

// ── Streaming Events ──

export type StreamEventType =
  | "analysis_start"
  | "analysis_done"
  | "kb_search_done"
  | "reply_chunk"
  | "tool_call"
  | "done";

export interface AnalysisDoneData {
  sentiment: string;
  ai_category: string;
  ai_priority: string;
  need_human: boolean;
  analysis_reason: string;
}

export interface KbSearchDoneData {
  count: number;
  sources: string[];
}

export interface ReplyChunkData {
  content: string;
}

export interface ToolCallData {
  tool: string;
  input: Record<string, unknown>;
  output: Record<string, unknown>;
}

export interface StreamDoneData {
  reply: string;
  tool_calls: ToolCallData[];
  kb_sources: string[];
  need_human: boolean;
}

export interface BatchAgentRunResponse {
  processed: number;
  results: AgentRunResult[];
}
