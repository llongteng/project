"""Lightweight knowledge base search — keyword-based, no vector DB."""

from sqlalchemy.orm import Session

from models import KnowledgeBase, TicketCategory


def search_kb(
    db: Session,
    query: str,
    category: str | None = None,
    limit: int = 5,
    min_score: float = 0,
) -> list[KnowledgeBase]:
    """Search knowledge base by keyword + text matching.

    Scoring:
        keyword field match  -> weight 3
        title match          -> weight 2
        content match        -> weight 1
    """
    entries = db.query(KnowledgeBase).filter(KnowledgeBase.enabled == 1)
    if category:
        try:
            cat = TicketCategory(category)
            entries = entries.filter(KnowledgeBase.category == cat)
        except ValueError:
            pass

    entries = entries.all()

    scored: list[tuple[float, KnowledgeBase]] = []
    for entry in entries:
        score = _score_entry(query, entry)
        if score > min_score:  # require at least some match
            scored.append((score, entry))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [e for _, e in scored[:limit]]


def _score_entry(query: str, entry: KnowledgeBase) -> float:
    q = query.lower()
    score = 0.0

    # Keyword match (high weight) — comma or space separated
    for kw in entry.keywords.replace(",", " ").split():
        kw = kw.strip().lower()
        if kw and kw in q:
            score += 3

    # Title match
    if q and q in entry.title.lower():
        score += 2

    # Content match — count occurrences of query words
    content_lower = entry.content.lower()
    for word in q.split():
        if len(word) >= 2:
            score += content_lower.count(word) * 0.5

    return score


def build_reply_text(
    ticket_title: str,
    analysis_result: dict,
    kb_entries: list[KnowledgeBase],
) -> str:
    """Compose a reply by combining knowledge base content with analysis context."""

    sentiment = analysis_result.get("sentiment", "normal")
    need_human = analysis_result.get("need_human", False)

    parts = []

    # Greeting based on sentiment
    if sentiment in ("angry", "complaint"):
        parts.append("非常抱歉给您带来不便。")
    elif sentiment == "anxious":
        parts.append("您好，我们理解您的急切心情。")
    else:
        parts.append("您好，感谢您的来信。")

    # If need human, mention escalation
    if need_human:
        parts.append("您的问题我们已经升级至人工客服优先处理。")

    # Knowledge base content
    if kb_entries:
        parts.append("根据我们的政策和流程：")
        for i, entry in enumerate(kb_entries[:3], 1):
            parts.append(f"\n{i}. {entry.content}")
        parts.append(f"\n\n参考来源: {', '.join(e.title for e in kb_entries[:3])}")
    else:
        parts.append(
            "关于您的问题，我们暂时没有找到对应的知识库内容。"
            "客服人员会尽快跟进处理，请您耐心等待。"
        )

    parts.append("\n\n如有其他问题，请随时联系我们。")

    return "".join(parts)
