from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from schemas import StatsOverview, CategoryBreakdown, KnowledgeGap, FrequentIssuesResponse
from services.ticket_summarizer import compute_stats

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/overview", response_model=StatsOverview)
def analytics_overview(db: Session = Depends(get_db)):
    stats = compute_stats(db)
    return StatsOverview(**stats["overview"])


@router.get("/frequent-issues", response_model=FrequentIssuesResponse)
def analytics_frequent_issues(db: Session = Depends(get_db)):
    stats = compute_stats(db)
    keywords = [g["search_query"] for g in stats["knowledge_gaps"][:10]]
    return FrequentIssuesResponse(
        keywords=keywords,
        categories=[CategoryBreakdown(**item) for item in stats["category_breakdown"]],
        suggested_kb_gaps=[KnowledgeGap(**item) for item in stats["knowledge_gaps"]],
    )
