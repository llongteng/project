from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models import KnowledgeBase, TicketCategory
from schemas import KBCreate, KBUpdate, KBResponse
from services.knowledge_base import search_kb

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.get("", response_model=list[KBResponse])
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


@router.get("/search", response_model=list[KBResponse])
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


@router.post("", response_model=KBResponse, status_code=201)
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


@router.patch("/{kb_id}", response_model=KBResponse)
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


@router.delete("/{kb_id}", status_code=204)
def delete_knowledge(kb_id: int, db: Session = Depends(get_db)):
    entry = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="知识条目不存在")
    db.delete(entry)
    db.commit()
