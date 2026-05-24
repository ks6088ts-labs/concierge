from __future__ import annotations

from typing import Protocol

from concierge.knowledge.domain.entities import KnowledgeChunk, KnowledgeSearchResult
from concierge.knowledge.domain.value_objects import CollectionName


class KnowledgeRepository(Protocol):
    def upsert_chunks(self, chunks: list[KnowledgeChunk]) -> int: ...

    def count_chunks(self, collection: CollectionName) -> int: ...

    def drop_collection(self, collection: CollectionName) -> None: ...

    def search(self, collection: CollectionName, query: str, k: int = 4) -> list[KnowledgeSearchResult]: ...
