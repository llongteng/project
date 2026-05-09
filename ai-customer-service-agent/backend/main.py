from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database import engine, get_db, SessionLocal, Base
from sqlalchemy import inspect, text
from models import (
    Ticket,
    Message,
    TicketStatus,
    TicketPriority,
    TicketCategory,
    MessageRole,
    AnalysisStatus,
    KnowledgeBase,
    TicketSummary,
)
from schemas import (
    TicketCreate,
    TicketStatusUpdate,
    TicketListResponse,
    TicketDetailResponse,
    MessageCreate,
    MessageResponse,
    KBCreate,
    KBUpdate,
    KBResponse,
    TicketSummaryResponse,
    StatsOverview,
    CategoryBreakdown,
    EscalationReason,
    KnowledgeGap,
    FrequentIssuesResponse,
    AgentRunResult,
    BatchAgentRunResponse,
    ToolCallRecord,
)
import json
import logging
import os

from sse_starlette.sse import EventSourceResponse

from services.ticket_analyzer import get_analyzer, RuleBasedAnalyzer
from services.knowledge_base import search_kb, build_reply_text
from services.ticket_summarizer import generate_summary, compute_stats
from services.llm_client import get_llm_client
from services.embedding_service import get_embedding_service
from services.reply_generator import get_reply_generator
from services.tool_registry import get_tool_definitions, execute_tool

logger = logging.getLogger(__name__)

app = FastAPI(title="AI Customer Service Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    _migrate_source_kb_ids()
    _migrate_embedding_column()
    db = SessionLocal()
    try:
        get_embedding_service().load_all(db)
    except Exception as e:
        logger.warning("Failed to load embeddings on startup: %s", e)
    finally:
        db.close()


def _migrate_source_kb_ids():
    """Add source_kb_ids column if it doesn't exist (SQLite compat)."""
    inspector = inspect(engine)
    columns = [c["name"] for c in inspector.get_columns("messages")]
    if "source_kb_ids" not in columns:
        with engine.connect() as conn:
            conn.execute(text(
                "ALTER TABLE messages ADD COLUMN source_kb_ids VARCHAR(500) DEFAULT ''"
            ))
            conn.commit()


def _migrate_embedding_column():
    """Add embedding column to knowledge_base if it doesn't exist."""
    inspector = inspect(engine)
    columns = [c["name"] for c in inspector.get_columns("knowledge_base")]
    if "embedding" not in columns:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE knowledge_base ADD COLUMN embedding TEXT"))
            conn.commit()


# ── Ticket endpoints ──

@app.post("/api/tickets", response_model=TicketDetailResponse, status_code=201)
def create_ticket(body: TicketCreate, db: Session = Depends(get_db)):
    ticket = Ticket(
        title=body.title,
        customer_name=body.customer_name,
        customer_email=body.customer_email,
        category=body.category,
        priority=body.priority,
        status=TicketStatus.PENDING,
    )
    db.add(ticket)
    db.flush()

    db.add(
        Message(
            ticket_id=ticket.id,
            role=MessageRole.USER,
            content=body.initial_message,
        )
    )
    db.add(
        Message(
            ticket_id=ticket.id,
            role=MessageRole.SYSTEM,
            content="工单已创建，等待处理。",
        )
    )
    db.commit()

    # Auto-trigger AI analysis
    try:
        result = _analyze_with_fallback(body.title, body.initial_message)
        ticket.sentiment = result.sentiment
        ticket.ai_category = result.ai_category
        ticket.ai_priority = result.ai_priority
        ticket.need_human = 1 if result.need_human else 0
        ticket.analysis_reason = result.reason
        ticket.analysis_status = AnalysisStatus.COMPLETED
        ticket.analyzed_at = datetime.utcnow()

        if result.need_human:
            ticket.status = TicketStatus.ESCALATED
            db.add(
                Message(
                    ticket_id=ticket.id,
                    role=MessageRole.SYSTEM,
                    content=(
                        f"AI 分析完成: 情绪={result.sentiment}, 分类={result.ai_category}, "
                        f"优先级={result.ai_priority}。判定需要人工介入，工单已自动升级。"
                    ),
                )
            )
        else:
            db.add(
                Message(
                    ticket_id=ticket.id,
                    role=MessageRole.SYSTEM,
                    content=(
                        f"AI 分析完成: 情绪={result.sentiment}, 分类={result.ai_category}, "
                        f"优先级={result.ai_priority}。无需人工介入，可按正常流程处理。"
                    ),
                )
            )
        db.commit()
    except Exception:
        ticket.analysis_status = AnalysisStatus.FAILED
        db.commit()

    db.refresh(ticket)
    return _to_detail(ticket)


@app.get("/api/tickets", response_model=list[TicketListResponse])
def list_tickets(
    status: str | None = Query(None),
    category: str | None = Query(None),
    priority: str | None = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Ticket)
    if status:
        q = q.filter(Ticket.status == status)
    if category:
        q = q.filter(Ticket.category == category)
    if priority:
        q = q.filter(Ticket.priority == priority)
    tickets = q.order_by(Ticket.updated_at.desc()).all()

    return [
        TicketListResponse(
            id=t.id,
            title=t.title,
            customer_name=t.customer_name,
            category=t.category.value if t.category else "other",
            priority=t.priority.value if t.priority else "medium",
            status=t.status.value if t.status else "pending",
            created_at=t.created_at,
            updated_at=t.updated_at,
            message_count=len(t.messages),
            sentiment=t.sentiment.value if t.sentiment else None,
            ai_category=t.ai_category.value if t.ai_category else None,
            ai_priority=t.ai_priority.value if t.ai_priority else None,
            need_human=bool(t.need_human),
        )
        for t in tickets
    ]


@app.get("/api/tickets/{ticket_id}", response_model=TicketDetailResponse)
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    return _to_detail(ticket)


@app.patch("/api/tickets/{ticket_id}/status", response_model=TicketDetailResponse)
def update_ticket_status(
    ticket_id: int, body: TicketStatusUpdate, db: Session = Depends(get_db)
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    ticket.status = body.status
    db.commit()
    db.refresh(ticket)

    db.add(
        Message(
            ticket_id=ticket.id,
            role=MessageRole.SYSTEM,
            content=f"工单状态已更新为: {ticket.status.value}",
        )
    )
    db.commit()
    db.refresh(ticket)

    if body.status in (TicketStatus.RESOLVED, TicketStatus.ESCALATED):
        generate_summary(db, ticket)
        db.refresh(ticket)

    return _to_detail(ticket)


# ── Message endpoints ──

@app.post("/api/tickets/{ticket_id}/messages", response_model=MessageResponse, status_code=201)
def add_message(ticket_id: int, body: MessageCreate, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    msg = Message(ticket_id=ticket_id, role=body.role, content=body.content)
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


# ── Analysis endpoint ──

@app.post("/api/tickets/{ticket_id}/analyze", response_model=TicketDetailResponse)
def analyze_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")

    first_msg = (
        db.query(Message)
        .filter(Message.ticket_id == ticket_id, Message.role == MessageRole.USER)
        .order_by(Message.created_at)
        .first()
    )
    content = first_msg.content if first_msg else ""

    try:
        result = _analyze_with_fallback(ticket.title, content)
        ticket.sentiment = result.sentiment
        ticket.ai_category = result.ai_category
        ticket.ai_priority = result.ai_priority
        ticket.need_human = 1 if result.need_human else 0
        ticket.analysis_reason = result.reason
        ticket.analysis_status = AnalysisStatus.COMPLETED
        ticket.analyzed_at = datetime.utcnow()

        if result.need_human:
            ticket.status = TicketStatus.ESCALATED
            db.add(
                Message(
                    ticket_id=ticket.id,
                    role=MessageRole.SYSTEM,
                    content=(
                        f"重新分析完成: 情绪={result.sentiment}, 分类={result.ai_category}, "
                        f"优先级={result.ai_priority}。判定需要人工介入，工单已自动升级。"
                    ),
                )
            )
        else:
            db.add(
                Message(
                    ticket_id=ticket.id,
                    role=MessageRole.SYSTEM,
                    content=(
                        f"重新分析完成: 情绪={result.sentiment}, 分类={result.ai_category}, "
                        f"优先级={result.ai_priority}。无需人工介入。"
                    ),
                )
            )
        db.commit()
        db.refresh(ticket)
        return _to_detail(ticket)
    except Exception as e:
        ticket.analysis_status = AnalysisStatus.FAILED
        ticket.analysis_reason = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


# ── Knowledge Base endpoints ──

@app.get("/api/knowledge", response_model=list[KBResponse])
def list_knowledge(
    category: str | None = Query(None),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
):
    if search:
        return [
            KBResponse(
                id=e.id,
                title=e.title,
                category=e.category.value if e.category else "other",
                content=e.content,
                keywords=e.keywords or "",
                enabled=bool(e.enabled),
                created_at=e.created_at,
                updated_at=e.updated_at,
            )
            for e in search_kb(db, search, category, limit=20)
        ]

    q = db.query(KnowledgeBase)
    if category:
        try:
            q = q.filter(KnowledgeBase.category == TicketCategory(category))
        except ValueError:
            pass
    entries = q.order_by(KnowledgeBase.updated_at.desc()).all()
    return [
        KBResponse(
            id=e.id,
            title=e.title,
            category=e.category.value if e.category else "other",
            content=e.content,
            keywords=e.keywords or "",
            enabled=bool(e.enabled),
            created_at=e.created_at,
            updated_at=e.updated_at,
        )
        for e in entries
    ]


@app.get("/api/knowledge/search", response_model=list[KBResponse])
def search_knowledge_endpoint(
    q: str = Query(..., min_length=1),
    category: str | None = Query(None),
    db: Session = Depends(get_db),
):
    entries = search_kb(db, q, category, limit=20)
    return [
        KBResponse(
            id=e.id,
            title=e.title,
            category=e.category.value if e.category else "other",
            content=e.content,
            keywords=e.keywords or "",
            enabled=bool(e.enabled),
            created_at=e.created_at,
            updated_at=e.updated_at,
        )
        for e in entries
    ]


@app.post("/api/knowledge", response_model=KBResponse, status_code=201)
def create_knowledge(body: KBCreate, db: Session = Depends(get_db)):
    entry = KnowledgeBase(
        title=body.title,
        category=body.category,
        content=body.content,
        keywords=body.keywords,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    try:
        get_embedding_service().update_entry(db, entry.id, entry.title, entry.content)
    except Exception:
        pass
    return KBResponse(
        id=entry.id,
        title=entry.title,
        category=entry.category.value if entry.category else "other",
        content=entry.content,
        keywords=entry.keywords or "",
        enabled=bool(entry.enabled),
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


@app.patch("/api/knowledge/{kb_id}", response_model=KBResponse)
def update_knowledge(kb_id: int, body: KBUpdate, db: Session = Depends(get_db)):
    entry = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="知识条目不存在")
    if body.title is not None:
        entry.title = body.title
    if body.category is not None:
        entry.category = body.category
    if body.content is not None:
        entry.content = body.content
    if body.keywords is not None:
        entry.keywords = body.keywords
    if body.enabled is not None:
        entry.enabled = 1 if body.enabled else 0
    db.commit()
    db.refresh(entry)
    try:
        get_embedding_service().update_entry(db, entry.id, entry.title, entry.content)
    except Exception:
        pass
    return KBResponse(
        id=entry.id,
        title=entry.title,
        category=entry.category.value if entry.category else "other",
        content=entry.content,
        keywords=entry.keywords or "",
        enabled=bool(entry.enabled),
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


@app.delete("/api/knowledge/{kb_id}", status_code=204)
def delete_knowledge(kb_id: int, db: Session = Depends(get_db)):
    entry = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="知识条目不存在")
    db.delete(entry)
    db.commit()


# ── Auto Reply endpoint ──

@app.post("/api/tickets/{ticket_id}/auto-reply", response_model=TicketDetailResponse)
def auto_reply(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")

    if ticket.status == TicketStatus.RESOLVED:
        raise HTTPException(status_code=400, detail="已解决的工单无法执行自动回复")

    first_msg = (
        db.query(Message)
        .filter(Message.ticket_id == ticket_id, Message.role == MessageRole.USER)
        .order_by(Message.created_at)
        .first()
    )
    user_content = first_msg.content if first_msg else ""

    # Ensure analysis is done
    if ticket.analysis_status != AnalysisStatus.COMPLETED:
        try:
            result = _analyze_with_fallback(ticket.title, user_content)
            ticket.sentiment = result.sentiment
            ticket.ai_category = result.ai_category
            ticket.ai_priority = result.ai_priority
            ticket.need_human = 1 if result.need_human else 0
            ticket.analysis_reason = result.reason
            ticket.analysis_status = AnalysisStatus.COMPLETED
            ticket.analyzed_at = datetime.utcnow()
            db.commit()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"前置分析失败: {str(e)}")

    analysis = {
        "sentiment": ticket.sentiment.value if ticket.sentiment else "normal",
        "need_human": bool(ticket.need_human),
        "ai_category": ticket.ai_category.value if ticket.ai_category else "other",
    }

    # Search knowledge base
    search_query = f"{ticket.title} {user_content}"
    kb_entries = search_kb(db, search_query, analysis["ai_category"], limit=5)
    hit_kb = len(kb_entries) > 0

    # Build reply
    reply = build_reply_text(ticket.title, analysis, kb_entries)

    # Save agent message
    agent_source_ids = ",".join(str(e.id) for e in kb_entries[:3]) if hit_kb else ""
    db.add(
        Message(
            ticket_id=ticket.id,
            role=MessageRole.AGENT,
            content=reply,
            source_kb_ids=agent_source_ids,
        )
    )

    # Build system message with match details
    if hit_kb:
        ticket.status = TicketStatus.ESCALATED if analysis["need_human"] else TicketStatus.WAITING_USER
        kb_summary = " | ".join(
            f"{e.title} (confidence≈{_format_confidence(e.id, kb_entries)})"
            for e in kb_entries[:3]
        )
        suggest_human = "建议人工介入" if analysis["need_human"] else "无需人工介入"
        sys_content = (
            f"自动回复已生成，命中{len(kb_entries)}条知识库: {kb_summary}。{suggest_human}。"
        )
    else:
        # No KB match → escalate to human
        ticket.need_human = 1
        ticket.status = TicketStatus.ESCALATED
        sys_content = (
            "自动回复：知识库未命中(no_match)，工单已自动升级至人工处理，"
            "建议人工介入。"
        )

    db.add(
        Message(
            ticket_id=ticket.id,
            role=MessageRole.SYSTEM,
            content=sys_content,
        )
    )
    db.commit()
    db.refresh(ticket)

    generate_summary(db, ticket)
    db.refresh(ticket)

    return _to_detail(ticket)


# ── Agent Workflow endpoints ──

@app.post("/api/tickets/{ticket_id}/agent-run", response_model=AgentRunResult)
def run_ticket_agent(
    ticket_id: int,
    force: bool = Query(False),
    db: Session = Depends(get_db),
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    if ticket.status == TicketStatus.RESOLVED:
        raise HTTPException(status_code=400, detail="已解决的工单无需再次运行 Agent")

    if not force and ticket.status in (TicketStatus.WAITING_USER, TicketStatus.ESCALATED):
        completed_marker = db.query(Message).filter(
            Message.ticket_id == ticket_id,
            Message.role == MessageRole.SYSTEM,
            Message.content.contains("[agent_run_completed]"),
        ).first()
        if completed_marker:
            raise HTTPException(
                status_code=400,
                detail="工单已有 Agent 处理记录，使用 force=true 强制重跑",
            )

    return _run_agent_workflow(db, ticket)


@app.post("/api/agent/batch-run", response_model=BatchAgentRunResponse)
def batch_run_agent(
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
):
    tickets = (
        db.query(Ticket)
        .filter(Ticket.status.in_([TicketStatus.PENDING, TicketStatus.AI_PROCESSING]))
        .order_by(Ticket.updated_at.desc())
        .limit(limit)
        .all()
    )
    results = []
    for ticket in tickets:
        try:
            results.append(_run_agent_workflow(db, ticket))
        except HTTPException:
            results.append(AgentRunResult(
                ticket_id=ticket.id,
                status=ticket.status.value if ticket.status else "pending",
                action="failed",
                need_human=bool(ticket.need_human),
                kb_hit=False,
                kb_sources=[],
                summary_id=None,
                steps=["运行失败"],
                tool_calls=[],
            ))
    return BatchAgentRunResponse(processed=len(results), results=results)


def _run_agent_workflow(db: Session, ticket: Ticket) -> AgentRunResult:
    steps = ["接收工单"]
    original_status = ticket.status

    tool_calls_made = []
    try:
        ticket.status = TicketStatus.AI_PROCESSING
        db.add(
            Message(
                ticket_id=ticket.id,
                role=MessageRole.SYSTEM,
                content="Agent 工作流已启动：开始分析问题、检索知识库并生成处理动作。",
            )
        )

        first_msg = (
            db.query(Message)
            .filter(Message.ticket_id == ticket.id, Message.role == MessageRole.USER)
            .order_by(Message.created_at)
            .first()
        )
        user_content = first_msg.content if first_msg else ""

        result = _analyze_with_fallback(ticket.title, user_content)
        ticket.sentiment = result.sentiment
        ticket.ai_category = result.ai_category
        ticket.ai_priority = result.ai_priority
        ticket.need_human = 1 if result.need_human else 0
        ticket.analysis_reason = result.reason
        ticket.analysis_status = AnalysisStatus.COMPLETED
        ticket.analyzed_at = datetime.utcnow()
        steps.append("完成问题分析")

        analysis = {
            "sentiment": result.sentiment.value if hasattr(result.sentiment, "value") else result.sentiment,
            "need_human": result.need_human,
            "ai_category": result.ai_category.value if hasattr(result.ai_category, "value") else result.ai_category,
        }
        kb_entries = search_kb(
            db,
            f"{ticket.title} {user_content}",
            analysis["ai_category"],
            limit=5,
        )

        # Hybrid: try embedding search too
        embedding_service = get_embedding_service()
        emb_entries = embedding_service.search(db, f"{ticket.title} {user_content}", limit=3)
        seen_ids = set()
        merged = []
        for entry, score in emb_entries:
            if entry.id not in seen_ids and entry.enabled:
                merged.append(entry)
                seen_ids.add(entry.id)
        for entry in kb_entries:
            if entry.id not in seen_ids:
                merged.append(entry)
                seen_ids.add(entry.id)
        kb_entries = merged[:5]

        kb_hit = len(kb_entries) > 0
        steps.append("完成知识库检索")

        # ── Tool Calling ──
        llm = get_llm_client()
        if llm.available:
            try:
                tool_msgs = [
                    {"role": "system", "content": "你是一个客服Agent，可以调用工具获取信息来帮助回答用户问题。请先调用必要的工具获取信息，之后再回复用户。"},
                    {"role": "user", "content": f"工单标题：{ticket.title}\n用户消息：{user_content}\n分析结果：分类={analysis['ai_category']}，情绪={analysis['sentiment']}"},
                ]
                response = llm.chat(
                    messages=tool_msgs,
                    tools=get_tool_definitions(),
                    tool_choice="auto",
                )
                msg = response.choices[0].message
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        tool_name = tc.function.name
                        tool_params = json.loads(tc.function.arguments)
                        tool_result = execute_tool(tool_name, tool_params, db)
                        tool_calls_made.append({
                            "tool": tool_name,
                            "input": tool_params,
                            "output": tool_result,
                        })
                    if tool_calls_made:
                        steps.append(f"执行工具调用 ({len(tool_calls_made)}个)")
            except Exception as e:
                logger.warning("Tool calling failed in agent workflow: %s", e)

        if kb_hit:
            reply = build_reply_text(ticket.title, analysis, kb_entries)
            db.add(
                Message(
                    ticket_id=ticket.id,
                    role=MessageRole.AGENT,
                    content=reply,
                    source_kb_ids=",".join(str(e.id) for e in kb_entries[:3]),
                )
            )
            source_text = "、".join(e.title for e in kb_entries[:3])
            ticket.status = TicketStatus.ESCALATED if ticket.need_human else TicketStatus.WAITING_USER
            action = "escalated_with_reply" if ticket.need_human else "replied_waiting_user"
            db.add(
                Message(
                    ticket_id=ticket.id,
                    role=MessageRole.SYSTEM,
                    content=(
                        f"Agent 已生成自动回复，引用知识库: {source_text}。"
                        f" [agent_run_completed]"
                    ),
                )
            )
            steps.append("生成自动回复")
        else:
            ticket.need_human = 1
            ticket.status = TicketStatus.ESCALATED
            action = "escalated_no_kb_match"
            db.add(
                Message(
                    ticket_id=ticket.id,
                    role=MessageRole.SYSTEM,
                    content=(
                        "Agent 未找到可引用知识库，已将工单升级人工处理。"
                        " [agent_run_completed]"
                    ),
                )
            )
            steps.append("升级人工处理")

        db.commit()
        db.refresh(ticket)

    except Exception as e:
        db.rollback()
        ticket.status = original_status
        ticket.analysis_status = AnalysisStatus.FAILED
        db.add(
            Message(
                ticket_id=ticket.id,
                role=MessageRole.SYSTEM,
                content=(
                    f"Agent 工作流运行失败: {str(e)}，工单状态已恢复。"
                    f" [agent_run_failed]"
                ),
            )
        )
        db.commit()
        raise HTTPException(
            status_code=500,
            detail=f"Agent 工作流运行失败: {str(e)}",
        )

    # Generate summary after successful commit (outside try/except)
    summary = None
    try:
        summary = generate_summary(db, ticket)
        db.refresh(ticket)
        steps.append("生成工单总结")
    except Exception:
        steps.append("总结生成失败（工作流已完成）")

    return AgentRunResult(
        ticket_id=ticket.id,
        status=ticket.status.value if ticket.status else "pending",
        action=action,
        need_human=bool(ticket.need_human),
        kb_hit=kb_hit,
        kb_sources=[e.title for e in kb_entries[:3]],
        summary_id=summary.id if summary else None,
        steps=steps,
        tool_calls=[
            ToolCallRecord(**tc) for tc in tool_calls_made
        ],
    )


def _format_confidence(entry_id: int, entries: list) -> str:
    """Format a rough confidence indicator based on position in ranked results."""
    for i, e in enumerate(entries):
        if e.id == entry_id:
            if i == 0:
                return "高"
            elif i <= 2:
                return "中"
            return "低"
    return "低"


# ── Ticket Summary endpoints ──


@app.post("/api/tickets/{ticket_id}/summarize", response_model=TicketSummaryResponse)
def summarize_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    summary = generate_summary(db, ticket)
    return summary


@app.get("/api/tickets/{ticket_id}/summary", response_model=TicketSummaryResponse)
def get_ticket_summary(ticket_id: int, db: Session = Depends(get_db)):
    summary = db.query(TicketSummary).filter(TicketSummary.ticket_id == ticket_id).first()
    if not summary:
        raise HTTPException(status_code=404, detail="该工单尚未生成总结")
    return summary


# ── Operational Statistics endpoints ──


@app.get("/api/stats/overview", response_model=StatsOverview)
def stats_overview(db: Session = Depends(get_db)):
    stats = compute_stats(db)
    return StatsOverview(**stats["overview"])


@app.get("/api/stats/categories", response_model=list[CategoryBreakdown])
def stats_categories(db: Session = Depends(get_db)):
    stats = compute_stats(db)
    return [CategoryBreakdown(**item) for item in stats["category_breakdown"]]


@app.get("/api/stats/escalations", response_model=list[EscalationReason])
def stats_escalations(db: Session = Depends(get_db)):
    stats = compute_stats(db)
    return [EscalationReason(**item) for item in stats["escalation_reasons"]]


@app.get("/api/stats/knowledge-gaps", response_model=list[KnowledgeGap])
def stats_knowledge_gaps(db: Session = Depends(get_db)):
    stats = compute_stats(db)
    return [KnowledgeGap(**item) for item in stats["knowledge_gaps"]]


# ── Compatibility endpoints ──


@app.post("/api/tickets/{ticket_id}/summary", response_model=TicketSummaryResponse)
def summarize_ticket_alias(ticket_id: int, db: Session = Depends(get_db)):
    """Alias for POST /api/tickets/{id}/summarize."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    return generate_summary(db, ticket)


@app.get("/api/analytics/overview", response_model=StatsOverview)
def analytics_overview(db: Session = Depends(get_db)):
    stats = compute_stats(db)
    return StatsOverview(**stats["overview"])


@app.get("/api/analytics/frequent-issues", response_model=FrequentIssuesResponse)
def analytics_frequent_issues(db: Session = Depends(get_db)):
    stats = compute_stats(db)
    # Top 10 keywords from knowledge gaps
    keywords = [g["search_query"] for g in stats["knowledge_gaps"][:10]]
    return FrequentIssuesResponse(
        keywords=keywords,
        categories=[CategoryBreakdown(**item) for item in stats["category_breakdown"]],
        suggested_kb_gaps=[KnowledgeGap(**item) for item in stats["knowledge_gaps"]],
    )


# ── Stream Reply endpoint (SSE) ──


@app.post("/api/tickets/{ticket_id}/stream-reply")
async def stream_reply(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    if ticket.status == TicketStatus.RESOLVED:
        raise HTTPException(status_code=400, detail="已解决的工单无法执行流式回复")

    first_msg = (
        db.query(Message)
        .filter(Message.ticket_id == ticket_id, Message.role == MessageRole.USER)
        .order_by(Message.created_at)
        .first()
    )
    user_content = first_msg.content if first_msg else ""

    async def event_generator():
        yield {"event": "analysis_start", "data": json.dumps({"ticket_id": ticket_id}, ensure_ascii=False)}

        result = _analyze_with_fallback(ticket.title, user_content)
        ticket.sentiment = result.sentiment
        ticket.ai_category = result.ai_category
        ticket.ai_priority = result.ai_priority
        ticket.need_human = 1 if result.need_human else 0
        ticket.analysis_reason = result.reason
        ticket.analysis_status = AnalysisStatus.COMPLETED
        ticket.analyzed_at = datetime.utcnow()
        db.commit()

        yield {"event": "analysis_done", "data": json.dumps(result.to_dict(), ensure_ascii=False)}

        analysis = {
            "sentiment": result.sentiment.value if hasattr(result.sentiment, "value") else result.sentiment,
            "need_human": result.need_human,
            "ai_category": result.ai_category.value if hasattr(result.ai_category, "value") else result.ai_category,
        }
        search_query = f"{ticket.title} {user_content}"
        kb_entries = search_kb(db, search_query, analysis["ai_category"], limit=5)

        embedding_service = get_embedding_service()
        emb_entries = embedding_service.search(db, search_query, limit=3)
        seen_ids = set()
        merged = []
        for entry, score in emb_entries:
            if entry.id not in seen_ids and entry.enabled:
                merged.append(entry)
                seen_ids.add(entry.id)
        for entry in kb_entries:
            if entry.id not in seen_ids:
                merged.append(entry)
                seen_ids.add(entry.id)
        kb_entries = merged[:5]

        yield {
            "event": "kb_search_done",
            "data": json.dumps(
                {"count": len(kb_entries), "sources": [e.title for e in kb_entries[:5]]},
                ensure_ascii=False,
            ),
        }

        tool_calls_log = []
        llm = get_llm_client()
        if llm.available:
            try:
                tool_msgs = [
                    {"role": "system", "content": "你是一个客服Agent，可以调用工具获取信息来帮助回答用户问题。请先调用必要的工具获取信息。"},
                    {"role": "user", "content": f"工单标题：{ticket.title}\n用户消息：{user_content}\n分析结果：分类={analysis['ai_category']}，情绪={analysis['sentiment']}"},
                ]
                response = llm.chat(
                    messages=tool_msgs,
                    tools=get_tool_definitions(),
                    tool_choice="auto",
                )
                msg = response.choices[0].message
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        tool_name = tc.function.name
                        tool_params = json.loads(tc.function.arguments)
                        tool_result = execute_tool(tool_name, tool_params, db)
                        tc_record = {"tool": tool_name, "input": tool_params, "output": tool_result}
                        tool_calls_log.append(tc_record)
                        yield {
                            "event": "tool_call",
                            "data": json.dumps(tc_record, ensure_ascii=False),
                        }
            except Exception as e:
                logger.warning("Tool calling failed in stream: %s", e)

        full_reply = ""
        generator = get_reply_generator()
        async for token in generator.generate_stream(ticket.title, analysis, kb_entries):
            full_reply += token
            yield {"event": "reply_chunk", "data": json.dumps({"content": token}, ensure_ascii=False)}

        # Save reply as agent message
        agent_source_ids = ",".join(str(e.id) for e in kb_entries[:3]) if kb_entries else ""
        db.add(
            Message(
                ticket_id=ticket.id,
                role=MessageRole.AGENT,
                content=full_reply,
                source_kb_ids=agent_source_ids,
            )
        )
        if ticket.need_human:
            ticket.status = TicketStatus.ESCALATED
        else:
            ticket.status = TicketStatus.WAITING_USER
        db.commit()

        yield {
            "event": "done",
            "data": json.dumps(
                {
                    "reply": full_reply,
                    "tool_calls": tool_calls_log,
                    "kb_sources": [e.title for e in kb_entries[:3]],
                    "need_human": bool(ticket.need_human),
                },
                ensure_ascii=False,
            ),
        }

    return EventSourceResponse(event_generator())


# ── Helpers ──

def _analyze_with_fallback(title: str, content: str):
    """Run analysis with LLM, falling back to rule-based on failure."""
    try:
        analyzer = get_analyzer()
        return analyzer.analyze(title, content)
    except Exception as e:
        logger.warning("LLM analysis failed, falling back to rule-based: %s", e)
        fallback = RuleBasedAnalyzer()
        return fallback.analyze(title, content)


def _to_detail(t: Ticket) -> TicketDetailResponse:
    return TicketDetailResponse(
        id=t.id,
        title=t.title,
        customer_name=t.customer_name,
        customer_email=t.customer_email,
        category=t.category.value if t.category else "other",
        priority=t.priority.value if t.priority else "medium",
        status=t.status.value if t.status else "pending",
        created_at=t.created_at,
        updated_at=t.updated_at,
        messages=[
            MessageResponse(
                id=m.id,
                ticket_id=m.ticket_id,
                role=m.role.value if m.role else "system",
                content=m.content,
                source_kb_ids=m.source_kb_ids or "",
                created_at=m.created_at,
            )
            for m in (t.messages or [])
        ],
        sentiment=t.sentiment.value if t.sentiment else None,
        ai_category=t.ai_category.value if t.ai_category else None,
        ai_priority=t.ai_priority.value if t.ai_priority else None,
        need_human=bool(t.need_human),
        analysis_reason=t.analysis_reason,
        analysis_status=t.analysis_status.value if t.analysis_status else None,
        analyzed_at=t.analyzed_at,
    )
