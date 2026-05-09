"""Embedding-based knowledge base search with in-memory cosine similarity."""

import json
import math
import os
import logging
from typing import List

from sqlalchemy.orm import Session

from models import KnowledgeBase

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self):
        self._vectors: dict[int, list[float]] = {}
        self._loaded = False
        self._rag_mode = os.getenv("RAG_MODE", "hybrid")

    def load_all(self, db: Session):
        from services.llm_client import get_llm_client

        llm = get_llm_client()
        entries = db.query(KnowledgeBase).filter(KnowledgeBase.enabled == 1).all()
        self._vectors = {}

        needs_embedding = []
        for entry in entries:
            if entry.embedding:
                try:
                    self._vectors[entry.id] = json.loads(entry.embedding)
                except (json.JSONDecodeError, TypeError):
                    needs_embedding.append(entry)
            else:
                needs_embedding.append(entry)

        if needs_embedding and llm.available:
            texts = [f"{e.title} {e.content}"[: llm.max_input_chars] for e in needs_embedding]
            try:
                embeddings = llm.embed(texts)
                for entry, vec in zip(needs_embedding, embeddings):
                    entry.embedding = json.dumps(vec)
                    self._vectors[entry.id] = vec
                db.commit()
                logger.info("Embedded %d KB entries", len(needs_embedding))
            except Exception as e:
                logger.warning("Failed to embed KB entries: %s. Will use keyword-only search.", e)
        elif needs_embedding:
            logger.warning("%d KB entries need embedding but LLM is disabled", len(needs_embedding))

        self._loaded = True

    def update_entry(self, db: Session, kb_id: int, title: str, content: str):
        from services.llm_client import get_llm_client

        llm = get_llm_client()
        if not llm.available:
            return
        text = f"{title} {content}"[: llm.max_input_chars]
        try:
            embeddings = llm.embed([text])
            vec = embeddings[0]
            entry = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
            if entry:
                entry.embedding = json.dumps(vec)
                db.commit()
            self._vectors[kb_id] = vec
        except Exception as e:
            logger.warning("Failed to embed KB entry %d: %s", kb_id, e)

    def search(
        self, db: Session, query: str, limit: int = 5
    ) -> list[tuple[KnowledgeBase, float]]:
        from services.llm_client import get_llm_client

        llm = get_llm_client()
        if not self._vectors or not llm.available:
            return []

        try:
            query_embeddings = llm.embed([query[: llm.max_input_chars]])
            query_vec = query_embeddings[0]
        except Exception as e:
            logger.warning("Failed to embed query: %s", e)
            return []

        results = []
        for kb_id, kb_vec in self._vectors.items():
            sim = self._cosine_similarity(query_vec, kb_vec)
            results.append((kb_id, sim))

        results.sort(key=lambda x: x[1], reverse=True)
        top = results[:limit]

        ids = [r[0] for r in top]
        entries = db.query(KnowledgeBase).filter(KnowledgeBase.id.in_(ids)).all()
        entry_map = {e.id: e for e in entries}

        return [(entry_map[eid], score) for eid, score in top if eid in entry_map]

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


_instance: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    global _instance
    if _instance is None:
        _instance = EmbeddingService()
    return _instance
