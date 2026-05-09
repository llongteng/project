"""Rule-based ticket summarizer — no LLM dependency."""

from datetime import datetime

from sqlalchemy.orm import Session

from models import Ticket, Message, MessageRole, TicketSummary, TicketStatus


CATEGORY_LABELS: dict[str, str] = {
    "order": "订单问题",
    "refund": "退款/售后",
    "account": "账号问题",
    "product": "产品使用",
    "complaint": "投诉建议",
    "other": "其他",
}

SENTIMENT_LABELS: dict[str, str] = {
    "normal": "正常",
    "anxious": "焦急",
    "angry": "生气",
    "complaint": "严重投诉",
}

STATUS_LABELS: dict[str, str] = {
    "pending": "待处理",
    "ai_processing": "AI处理中",
    "waiting_user": "等待用户回复",
    "resolved": "已解决",
    "escalated": "已升级人工",
}


def generate_summary(db: Session, ticket: Ticket) -> TicketSummary:
    """Generate or update a summary for the given ticket."""

    category = (ticket.ai_category.value if ticket.ai_category
                else ticket.category.value if ticket.category
                else "other")
    sentiment = ticket.sentiment.value if ticket.sentiment else "normal"
    final_status = ticket.status.value if ticket.status else "pending"

    # Problem description from first user message
    first_msg = (db.query(Message)
                 .filter(Message.ticket_id == ticket.id, Message.role == MessageRole.USER)
                 .order_by(Message.created_at)
                 .first())
    problem = first_msg.content if first_msg else ticket.title

    # Resolution from agent messages
    agent_msgs = (db.query(Message)
                  .filter(Message.ticket_id == ticket.id, Message.role == MessageRole.AGENT)
                  .order_by(Message.created_at)
                  .all())
    if agent_msgs:
        resolution = agent_msgs[-1].content[:500]
    elif final_status == "resolved":
        resolution = "工单已解决"
    else:
        resolution = f"工单当前状态: {STATUS_LABELS.get(final_status, final_status)}"

    # Escalation reason
    if ticket.need_human:
        reasons = []
        if ticket.sentiment and ticket.sentiment.value in ("angry", "complaint"):
            reasons.append(f"用户情绪{SENTIMENT_LABELS.get(sentiment, sentiment)}")
        if ticket.ai_priority and ticket.ai_priority.value in ("urgent", "high"):
            reasons.append(f"优先级为{ticket.ai_priority.value}")
        if ticket.ai_category and ticket.ai_category.value == "complaint":
            reasons.append("投诉类问题")
        if ticket.analysis_reason:
            reasons.append(ticket.analysis_reason)
        escalation_reason = "; ".join(reasons) if reasons else "AI分析判定需人工介入"
    else:
        escalation_reason = ""

    # Whether knowledge base was used — check structured source_kb_ids on agent messages
    agent_msgs = db.query(Message).filter(
        Message.ticket_id == ticket.id,
        Message.role == MessageRole.AGENT,
    ).all()

    kb_used_from_source = any(
        m.source_kb_ids and m.source_kb_ids.strip()
        for m in agent_msgs
    )

    if kb_used_from_source:
        knowledge_used = 1
    else:
        # Fallback to old text-based detection for legacy messages without source_kb_ids
        kb_msgs = (db.query(Message)
                   .filter(Message.ticket_id == ticket.id,
                           Message.role == MessageRole.SYSTEM,
                           Message.content.contains("命中") | Message.content.contains("引用"))
                   .all())
        kb_hit_msgs = [m for m in kb_msgs if "未命中" not in m.content and "no_match" not in m.content.lower()]
        knowledge_used = 1 if kb_hit_msgs else 0

    # Compose summary text
    parts = [
        f"【问题】{problem[:300]}",
        f"【分类】{CATEGORY_LABELS.get(category, category)}",
        f"【情绪】{SENTIMENT_LABELS.get(sentiment, sentiment)}",
        f"【最终状态】{STATUS_LABELS.get(final_status, final_status)}",
    ]
    if ticket.need_human:
        parts.append(f"【人工介入】是 ({escalation_reason[:200]})")
    else:
        parts.append("【人工介入】否")
    parts.append(f"【知识库】{'已使用' if knowledge_used else '未使用'}")
    parts.append(f"【处理结果】{resolution[:300]}")
    parts.append(f"【消息数】{len(ticket.messages or [])}")
    parts.append(f"【总结时间】{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")

    summary_text = "\n".join(parts)

    # Upsert: update existing or create new
    existing = (db.query(TicketSummary)
                .filter(TicketSummary.ticket_id == ticket.id)
                .first())
    if existing:
        existing.problem = problem[:300]
        existing.category = category
        existing.sentiment = sentiment
        existing.resolution = resolution[:500]
        existing.final_status = final_status
        existing.need_human = ticket.need_human
        existing.escalation_reason = escalation_reason[:200]
        existing.knowledge_used = knowledge_used
        existing.summary_text = summary_text
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing
    else:
        summary = TicketSummary(
            ticket_id=ticket.id,
            problem=problem[:300],
            category=category,
            sentiment=sentiment,
            resolution=resolution[:500],
            final_status=final_status,
            need_human=ticket.need_human,
            escalation_reason=escalation_reason[:200],
            knowledge_used=knowledge_used,
            summary_text=summary_text,
        )
        db.add(summary)
        db.commit()
        db.refresh(summary)
        return summary


def compute_stats(db: Session) -> dict:
    """Compute operational statistics from the database."""

    tickets = db.query(Ticket).all()
    summaries = db.query(TicketSummary).all()
    summary_by_ticket = {s.ticket_id: s for s in summaries}

    total = len(tickets)
    resolved = sum(1 for t in tickets if t.status.value == "resolved")
    escalated = sum(1 for t in tickets if t.need_human)
    escalation_rate = escalated / total if total > 0 else 0.0

    # KB hit rate: among auto-replied tickets, how many used KB
    kb_used = sum(1 for s in summaries if s.knowledge_used)
    kb_total = len(summaries)
    kb_hit_rate = kb_used / kb_total if kb_total > 0 else 0.0

    # Average messages per resolved ticket
    resolved_tickets = [t for t in tickets if t.status.value == "resolved"]
    total_msgs = sum(len(t.messages or []) for t in resolved_tickets)
    avg_msgs = total_msgs / len(resolved_tickets) if resolved_tickets else 0.0

    overview = {
        "total_tickets": total,
        "resolved_tickets": resolved,
        "escalated_tickets": escalated,
        "escalation_rate": round(escalation_rate, 3),
        "kb_hit_rate": round(kb_hit_rate, 3),
        "avg_resolution_messages": round(avg_msgs, 1),
    }

    # Category breakdown
    cat_counts: dict[str, int] = {}
    for t in tickets:
        cat = t.ai_category.value if t.ai_category else (t.category.value if t.category else "other")
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
    category_breakdown = [
        {"category": k, "count": v}
        for k, v in sorted(cat_counts.items(), key=lambda x: x[1], reverse=True)
    ]

    # Escalation reasons
    esc_reasons: dict[str, int] = {}
    for s in summaries:
        if s.need_human and s.escalation_reason:
            esc_reasons[s.escalation_reason] = esc_reasons.get(s.escalation_reason, 0) + 1
    escalation_reasons = [
        {"reason": k, "count": v}
        for k, v in sorted(esc_reasons.items(), key=lambda x: x[1], reverse=True)[:10]
    ]

    # Knowledge gaps: find tickets where KB was not used
    gaps: dict[str, dict] = {}
    for s in summaries:
        if not s.knowledge_used:
            key = s.problem[:80]
            if key not in gaps:
                gaps[key] = {"search_query": key, "ticket_count": 0, "suggested_category": s.category}
            gaps[key]["ticket_count"] += 1
    knowledge_gaps = sorted(gaps.values(), key=lambda x: x["ticket_count"], reverse=True)[:10]

    return {
        "overview": overview,
        "category_breakdown": category_breakdown,
        "escalation_reasons": escalation_reasons,
        "knowledge_gaps": knowledge_gaps,
    }
