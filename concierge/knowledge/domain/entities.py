from __future__ import annotations

from dataclasses import dataclass

from concierge.knowledge.domain.value_objects import ChunkId, CollectionName, ContentHash


@dataclass(frozen=True)
class KnowledgeDocument:
    source: str
    content: str


@dataclass(frozen=True)
class KnowledgeChunk:
    id: ChunkId
    collection: CollectionName
    source: str
    chunk_index: int
    content: str
    content_sha256: ContentHash
    ingested_at: str

    @property
    def metadata(self) -> dict[str, object]:
        return {
            "source": self.source,
            "collection": str(self.collection),
            "content_sha256": str(self.content_sha256),
            "chunk_index": self.chunk_index,
            "ingested_at": self.ingested_at,
        }


@dataclass(frozen=True)
class KnowledgeSearchResult:
    id: str
    content: str
    metadata: dict[str, object]
