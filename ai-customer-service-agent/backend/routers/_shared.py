from models import Ticket, MessageRole
from schemas import TicketDetailResponse, MessageResponse


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


def _format_confidence(entry_id: int, entries: list) -> str:
    for i, e in enumerate(entries):
        if e.id == entry_id:
            if i == 0:
                return "高"
            elif i <= 2:
                return "中"
            return "低"
    return "低"
