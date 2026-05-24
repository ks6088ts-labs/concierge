from __future__ import annotations

from functools import lru_cache

from concierge.knowledge.application.use_cases import DeleteCollection, IngestMarkdown, SearchKnowledge
from concierge.settings import KnowledgeTarget


@lru_cache(maxsize=32)
def get_search_knowledge_use_case(
    collection: str,
    target: KnowledgeTarget = KnowledgeTarget.DOCKER,
) -> SearchKnowledge:
    from concierge.knowledge.domain.value_objects import CollectionName
    from concierge.knowledge.infrastructure.embeddings.factory import create_embeddings
    from concierge.knowledge.infrastructure.persistence.factory import get_knowledge_repository

    resolved_collection = CollectionName(collection)
    repository = get_knowledge_repository(
        collection=resolved_collection,
        target=target,
        embeddings=create_embeddings(),
    )
    return SearchKnowledge(repository)


__all__ = [
    "DeleteCollection",
    "IngestMarkdown",
    "SearchKnowledge",
    "get_search_knowledge_use_case",
]
