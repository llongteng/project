from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models import (
    Ticket,
    Message,
    TicketStatus,
    TicketPriority,
    TicketCategory,
    MessageRole,
    AnalysisStatus,
    TicketSummary,
)
from schemas import (
    TicketCreate,
    TicketStatusUpdate,
    TicketListResponse,
    TicketDetailResponse,
    MessageCreate,
    MessageResponse,
    TicketSummaryResponse,
)
from services.ticket_analyzer import get_analyzer
from services.knowledge_base import search_kb, build_reply_text
from services.ticket_summarizer import generate_summary
from routers._shared import _to_detail, _format_confidence

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


@router.post("", response_model=TicketDetailResponse, status_code=201)
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

    db.add(Message(
        ticket_id=ticket.id,
        role=MessageRole.USER,
        content=body.initial_message,
    ))
    db.add(Message(
        ticket_id=ticket.id,
        role=MessageRole.SYSTEM,
        content="工单已创建，等待处理。",
    ))
    db.commit()

    try:
        analyzer = get_analyzer()
        result = analyzer.analyze(body.title, body.initial_message)
        ticket.sentiment = result.sentiment
        ticket.ai_category = result.ai_category
        ticket.ai_priority = result.ai_priority
        ticket.need_human = 1 if result.need_human else 0
        ticket.analysis_reason = result.reason
        ticket.analysis_status = AnalysisStatus.COMPLETED
        ticket.analyzed_at = datetime.utcnow()

        if result.need_human:
            ticket.status = TicketStatus.ESCALATED
            db.add(Message(
                ticket_id=ticket.id,
                role=MessageRole.SYSTEM,
                content=(
                    f"AI 分析完成: 情绪={result.sentiment}, 分类={result.ai_category}, "
                    f"优先级={result.ai_priority}。判定需要人工介入，工单已自动升级。"
                ),
            ))
        else:
            db.add(Message(
                ticket_id=ticket.id,
                role=MessageRole.SYSTEM,
                content=(
                    f"AI 分析完成: 情绪={result.sentiment}, 分类={result.ai_category}, "
                    f"优先级={result.ai_priority}。无需人工介入，可按正常流程处理。"
                ),
            ))
        db.commit()
    except Exception:
        ticket.analysis_status = AnalysisStatus.FAILED
        db.commit()

    db.refresh(ticket)
    return _to_detail(ticket)


@router.get("", response_model=list[TicketListResponse])
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


@router.get("/{ticket_id}", response_model=TicketDetailResponse)
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    return _to_detail(ticket)


@router.patch("/{ticket_id}/status", response_model=TicketDetailResponse)
def update_ticket_status(
    ticket_id: int, body: TicketStatusUpdate, db: Session = Depends(get_db)
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    ticket.status = body.status
    db.commit()
    db.refresh(ticket)

    db.add(Message(
        ticket_id=ticket.id,
        role=MessageRole.SYSTEM,
        content=f"工单状态已更新为: {ticket.status.value}",
    ))
    db.commit()
    db.refresh(ticket)

    if body.status in (TicketStatus.RESOLVED, TicketStatus.ESCALATED):
        generate_summary(db, ticket)
        db.refresh(ticket)

    return _to_detail(ticket)


@router.post("/{ticket_id}/messages", response_model=MessageResponse, status_code=201)
def add_message(ticket_id: int, body: MessageCreate, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    msg = Message(ticket_id=ticket_id, role=body.role, content=body.content)
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


@router.post("/{ticket_id}/analyze", response_model=TicketDetailResponse)
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
        analyzer = get_analyzer()
        result = analyzer.analyze(ticket.title, content)
        ticket.sentiment = result.sentiment
        ticket.ai_category = result.ai_category
        ticket.ai_priority = result.ai_priority
        ticket.need_human = 1 if result.need_human else 0
        ticket.analysis_reason = result.reason
        ticket.analysis_status = AnalysisStatus.COMPLETED
        ticket.analyzed_at = datetime.utcnow()

        if result.need_human:
            ticket.status = TicketStatus.ESCALATED
            db.add(Message(
                ticket_id=ticket.id,
                role=MessageRole.SYSTEM,
                content=(
                    f"重新分析完成: 情绪={result.sentiment}, 分类={result.ai_category}, "
                    f"优先级={result.ai_priority}。判定需要人工介入，工单已自动升级。"
                ),
            ))
        else:
            db.add(Message(
                ticket_id=ticket.id,
                role=MessageRole.SYSTEM,
                content=(
                    f"重新分析完成: 情绪={result.sentiment}, 分类={result.ai_category}, "
                    f"优先级={result.ai_priority}。无需人工介入。"
                ),
            ))
        db.commit()
        db.refresh(ticket)
        return _to_detail(ticket)
    except Exception as e:
        ticket.analysis_status = AnalysisStatus.FAILED
        ticket.analysis_reason = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@router.post("/{ticket_id}/auto-reply", response_model=TicketDetailResponse)
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

    if ticket.analysis_status != AnalysisStatus.COMPLETED:
        try:
            analyzer = get_analyzer()
            result = analyzer.analyze(ticket.title, user_content)
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

    search_query = f"{ticket.title} {user_content}"
    kb_entries = search_kb(db, search_query, analysis["ai_category"], limit=5)
    hit_kb = len(kb_entries) > 0

    reply = build_reply_text(ticket.title, analysis, kb_entries)

    agent_source_ids = ",".join(str(e.id) for e in kb_entries[:3]) if hit_kb else ""
    db.add(Message(
        ticket_id=ticket.id,
        role=MessageRole.AGENT,
        content=reply,
        source_kb_ids=agent_source_ids,
    ))

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
        ticket.need_human = 1
        ticket.status = TicketStatus.ESCALATED
        sys_content = (
            "自动回复：知识库未命中(no_match)，工单已自动升级至人工处理，"
            "建议人工介入。"
        )

    db.add(Message(
        ticket_id=ticket.id,
        role=MessageRole.SYSTEM,
        content=sys_content,
    ))
    db.commit()
    db.refresh(ticket)

    generate_summary(db, ticket)
    db.refresh(ticket)

    return _to_detail(ticket)


@router.post("/{ticket_id}/summarize", response_model=TicketSummaryResponse)
def summarize_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    summary = generate_summary(db, ticket)
    return summary


@router.get("/{ticket_id}/summary", response_model=TicketSummaryResponse)
def get_ticket_summary(ticket_id: int, db: Session = Depends(get_db)):
    summary = db.query(TicketSummary).filter(TicketSummary.ticket_id == ticket_id).first()
    if not summary:
        raise HTTPException(status_code=404, detail="该工单尚未生成总结")
    return summary


# Compatibility alias: POST /api/tickets/{ticket_id}/summary
@router.post("/{ticket_id}/summary", response_model=TicketSummaryResponse)
def summarize_ticket_alias(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    return generate_summary(db, ticket)
