const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function fetchTickets(params?: {
  status?: string;
  category?: string;
  priority?: string;
}) {
  const searchParams = new URLSearchParams();
  if (params?.status) searchParams.set("status", params.status);
  if (params?.category) searchParams.set("category", params.category);
  if (params?.priority) searchParams.set("priority", params.priority);

  const res = await fetch(`${API_BASE}/api/tickets?${searchParams.toString()}`);
  if (!res.ok) throw new Error("Failed to fetch tickets");
  return res.json();
}

export async function fetchTicket(id: number) {
  const res = await fetch(`${API_BASE}/api/tickets/${id}`);
  if (!res.ok) throw new Error("Ticket not found");
  return res.json();
}

export async function createTicket(data: {
  title: string;
  customer_name: string;
  customer_email: string;
  category: string;
  priority: string;
  initial_message: string;
}) {
  const res = await fetch(`${API_BASE}/api/tickets`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Failed to create ticket");
  }
  return res.json();
}

export async function updateTicketStatus(id: number, status: string) {
  const res = await fetch(`${API_BASE}/api/tickets/${id}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  if (!res.ok) throw new Error("Failed to update status");
  return res.json();
}

export async function analyzeTicket(ticketId: number) {
  const res = await fetch(`${API_BASE}/api/tickets/${ticketId}/analyze`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("Failed to analyze ticket");
  return res.json();
}

export async function fetchKnowledge(params?: {
  category?: string;
  search?: string;
}) {
  const searchParams = new URLSearchParams();
  if (params?.category) searchParams.set("category", params.category);
  if (params?.search) searchParams.set("search", params.search);

  const res = await fetch(
    `${API_BASE}/api/knowledge?${searchParams.toString()}`
  );
  if (!res.ok) throw new Error("Failed to fetch knowledge base");
  return res.json();
}

export async function createKnowledge(data: {
  title: string;
  category: string;
  content: string;
  keywords: string;
}) {
  const res = await fetch(`${API_BASE}/api/knowledge`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Failed to create knowledge");
  }
  return res.json();
}

export async function updateKnowledge(
  id: number,
  data: {
    title?: string;
    category?: string;
    content?: string;
    keywords?: string;
    enabled?: boolean;
  }
) {
  const res = await fetch(`${API_BASE}/api/knowledge/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to update knowledge");
  return res.json();
}

export async function deleteKnowledge(id: number) {
  const res = await fetch(`${API_BASE}/api/knowledge/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Failed to delete knowledge");
}

export async function autoReply(ticketId: number): Promise<import("./types").TicketDetail> {
  const res = await fetch(`${API_BASE}/api/tickets/${ticketId}/auto-reply`, {
    method: "POST",
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Failed to generate auto reply");
  }
  return res.json();
}

export async function addMessage(
  ticketId: number,
  data: { role: string; content: string }
) {
  const res = await fetch(`${API_BASE}/api/tickets/${ticketId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to add message");
  return res.json();
}

export async function generateSummary(ticketId: number): Promise<import("./types").TicketSummary> {
  const res = await fetch(`${API_BASE}/api/tickets/${ticketId}/summarize`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("Failed to generate summary");
  return res.json();
}

export async function fetchTicketSummary(ticketId: number): Promise<import("./types").TicketSummary | null> {
  const res = await fetch(`${API_BASE}/api/tickets/${ticketId}/summary`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error("Failed to fetch summary");
  return res.json();
}

export async function fetchStatsOverview(): Promise<import("./types").StatsOverview> {
  const res = await fetch(`${API_BASE}/api/stats/overview`);
  if (!res.ok) throw new Error("Failed to fetch stats");
  return res.json();
}

export async function fetchCategoryBreakdown(): Promise<import("./types").CategoryBreakdown[]> {
  const res = await fetch(`${API_BASE}/api/stats/categories`);
  if (!res.ok) throw new Error("Failed to fetch category stats");
  return res.json();
}

export async function fetchEscalationReasons(): Promise<import("./types").EscalationReasonItem[]> {
  const res = await fetch(`${API_BASE}/api/stats/escalations`);
  if (!res.ok) throw new Error("Failed to fetch escalation stats");
  return res.json();
}

export async function fetchKnowledgeGaps(): Promise<import("./types").KnowledgeGapItem[]> {
  const res = await fetch(`${API_BASE}/api/stats/knowledge-gaps`);
  if (!res.ok) throw new Error("Failed to fetch knowledge gaps");
  return res.json();
}

export async function fetchAnalyticsOverview(): Promise<import("./types").StatsOverview> {
  const res = await fetch(`${API_BASE}/api/analytics/overview`);
  if (!res.ok) throw new Error("Failed to fetch analytics overview");
  return res.json();
}

export async function fetchFrequentIssues(): Promise<import("./types").FrequentIssues> {
  const res = await fetch(`${API_BASE}/api/analytics/frequent-issues`);
  if (!res.ok) throw new Error("Failed to fetch frequent issues");
  return res.json();
}

export async function runAgentWorkflow(ticketId: number): Promise<import("./types").AgentRunResult> {
  const res = await fetch(`${API_BASE}/api/tickets/${ticketId}/agent-run`, {
    method: "POST",
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Failed to run agent workflow");
  }
  return res.json();
}

export async function streamAgentReply(
  ticketId: number,
  onEvent: (event: { event: string; data: unknown }) => void,
  onError: (error: Error) => void,
  onDone: () => void
): Promise<void> {
  try {
    const res = await fetch(
      `${API_BASE}/api/tickets/${ticketId}/stream-reply`,
      { method: "POST" }
    );

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Stream request failed" }));
      throw new Error(err.detail || "Stream request failed");
    }

    const reader = res.body?.getReader();
    if (!reader) {
      throw new Error("Response body is not readable");
    }

    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      // Normalize CRLF to LF for consistent SSE parsing
      buffer = buffer.replace(/\r\n/g, "\n");

      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() || "";

      for (const block of blocks) {
        const eventMatch = block.match(/^event: (.+)$/m);
        const dataMatch = block.match(/^data: (.+)$/m);
        if (eventMatch && dataMatch) {
          try {
            const parsed = JSON.parse(dataMatch[1]);
            onEvent({ event: eventMatch[1], data: parsed });
          } catch {
            // skip unparseable events
          }
        }
      }
    }

    onDone();
  } catch (err) {
    onError(err instanceof Error ? err : new Error(String(err)));
  }
}

export async function batchRunAgent(limit = 5): Promise<import("./types").BatchAgentRunResponse> {
  const res = await fetch(`${API_BASE}/api/agent/batch-run?limit=${limit}`, {
    method: "POST",
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Failed to run batch agent workflow");
  }
  return res.json();
}
