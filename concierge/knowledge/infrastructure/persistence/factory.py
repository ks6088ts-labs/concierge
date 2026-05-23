from __future__ import annotations

from langchain_core.embeddings import Embeddings

from concierge.knowledge.application.repositories import KnowledgeRepository
from concierge.knowledge.domain.value_objects import CollectionName
from concierge.knowledge.infrastructure.persistence.pgvector import create_pgvector_repository
from concierge.settings import KnowledgeTarget, KnowledgeVectorBackend, get_knowledge_settings


def get_knowledge_repository(
    *,
    collection: CollectionName,
    target: KnowledgeTarget,
    embeddings: Embeddings | None = None,
    ensure_collection: bool = False,
) -> KnowledgeRepository:
    settings = get_knowledge_settings()
    if settings.vector_backend is KnowledgeVectorBackend.PGVECTOR:
        return create_pgvector_repository(
            collection=collection,
            target=target,
            embeddings=embeddings,
            vector_size=settings.vector_size,
            ensure_collection=ensure_collection,
        )
    raise ValueError(f"Unhandled vector backend: {settings.vector_backend!r}")  # pragma: no cover
