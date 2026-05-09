from datetime import datetime
from pydantic import BaseModel, EmailStr, Field

from models import TicketCategory, TicketPriority, TicketStatus, MessageRole


# ── Ticket ──

class TicketCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    customer_name: str = Field(min_length=1, max_length=100)
    customer_email: EmailStr
    category: TicketCategory = TicketCategory.OTHER
    priority: TicketPriority = TicketPriority.MEDIUM
    initial_message: str = Field(min_length=1)


class TicketStatusUpdate(BaseModel):
    status: TicketStatus


class TicketListResponse(BaseModel):
    id: int
    title: str
    customer_name: str
    category: str
    priority: str
    status: str
    created_at: datetime
    updated_at: datetime
    message_count: int
    sentiment: str | None = None
    ai_category: str | None = None
    ai_priority: str | None = None
    need_human: bool = False

    class Config:
        from_attributes = True


class TicketDetailResponse(BaseModel):
    id: int
    title: str
    customer_name: str
    customer_email: str
    category: str
    priority: str
    status: str
    created_at: datetime
    updated_at: datetime
    messages: list["MessageResponse"] = []
    sentiment: str | None = None
    ai_category: str | None = None
    ai_priority: str | None = None
    need_human: bool = False
    analysis_reason: str | None = None
    analysis_status: str | None = None
    analyzed_at: datetime | None = None

    class Config:
        from_attributes = True


class AnalysisResponse(BaseModel):
    sentiment: str
    ai_category: str
    ai_priority: str
    need_human: bool
    analysis_reason: str
    analysis_status: str
    analyzed_at: datetime | None = None


# ── Message ──

class MessageCreate(BaseModel):
    role: MessageRole
    content: str = Field(min_length=1)


class MessageResponse(BaseModel):
    id: int
    ticket_id: int
    role: str
    content: str
    source_kb_ids: str = ""
    created_at: datetime

    class Config:
        from_attributes = True


# ── Knowledge Base ──

class KBCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    category: TicketCategory = TicketCategory.OTHER
    content: str = Field(min_length=1)
    keywords: str = Field(default="", max_length=500)


class KBUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    category: TicketCategory | None = None
    content: str | None = None
    keywords: str | None = Field(default=None, max_length=500)
    enabled: bool | None = None


class KBResponse(BaseModel):
    id: int
    title: str
    category: str
    content: str
    keywords: str
    enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── Auto Reply ──

class AutoReplyResponse(BaseModel):
    reply: str
    sources: list[KBResponse] = []


# ── Ticket Summary ──

class TicketSummaryResponse(BaseModel):
    id: int
    ticket_id: int
    problem: str
    category: str
    sentiment: str
    resolution: str
    final_status: str
    need_human: bool
    escalation_reason: str
    knowledge_used: bool
    summary_text: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── Operational Statistics ──

class StatsOverview(BaseModel):
    total_tickets: int
    resolved_tickets: int
    escalated_tickets: int
    escalation_rate: float
    kb_hit_rate: float
    avg_resolution_messages: float


class CategoryBreakdown(BaseModel):
    category: str
    count: int


class EscalationReason(BaseModel):
    reason: str
    count: int


class KnowledgeGap(BaseModel):
    search_query: str
    ticket_count: int
    suggested_category: str


class FrequentIssuesResponse(BaseModel):
    keywords: list[str]
    categories: list[CategoryBreakdown]
    suggested_kb_gaps: list[KnowledgeGap]


# ── Agent Workflow ──

class ToolCallRecord(BaseModel):
    tool: str
    input: dict
    output: dict


class AgentRunResult(BaseModel):
    ticket_id: int
    status: str
    action: str
    need_human: bool
    kb_hit: bool
    kb_sources: list[str]
    summary_id: int | None = None
    steps: list[str]
    tool_calls: list[ToolCallRecord] = []


class BatchAgentRunResponse(BaseModel):
    processed: int
    results: list[AgentRunResult]
