from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from schemas import StatsOverview, CategoryBreakdown, EscalationReason, KnowledgeGap
from services.ticket_summarizer import compute_stats

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/overview", response_model=StatsOverview)
def stats_overview(db: Session = Depends(get_db)):
    stats = compute_stats(db)
    return StatsOverview(**stats["overview"])


@router.get("/categories", response_model=list[CategoryBreakdown])
def stats_categories(db: Session = Depends(get_db)):
    stats = compute_stats(db)
    return [CategoryBreakdown(**item) for item in stats["category_breakdown"]]


@router.get("/escalations", response_model=list[EscalationReason])
def stats_escalations(db: Session = Depends(get_db)):
    stats = compute_stats(db)
    return [EscalationReason(**item) for item in stats["escalation_reasons"]]


@router.get("/knowledge-gaps", response_model=list[KnowledgeGap])
def stats_knowledge_gaps(db: Session = Depends(get_db)):
    stats = compute_stats(db)
    return [KnowledgeGap(**item) for item in stats["knowledge_gaps"]]
