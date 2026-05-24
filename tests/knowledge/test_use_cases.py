from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from concierge.knowledge.application.use_cases import DeleteCollection, IngestMarkdown, SearchKnowledge
from concierge.knowledge.domain.entities import KnowledgeChunk, KnowledgeDocument, KnowledgeSearchResult
from concierge.knowledge.domain.value_objects import ChunkId, CollectionName, ContentHash


class InMemoryKnowledgeRepository:
    def __init__(self, search_results: list[KnowledgeSearchResult] | None = None) -> None:
        self._records: dict[str, KnowledgeChunk] = {}
        self._search_results = search_results or []
        self.search_calls: list[tuple[CollectionName, str, int]] = []

    def upsert_chunks(self, chunks: list[KnowledgeChunk]) -> int:
        for chunk in chunks:
            self._records[str(chunk.id)] = chunk
        return len(chunks)

    def count_chunks(self, collection: CollectionName) -> int:
        return sum(1 for chunk in self._records.values() if chunk.collection == collection)

    def drop_collection(self, collection: CollectionName) -> None:
        self._records = {key: chunk for key, chunk in self._records.items() if chunk.collection != collection}

    def search(self, collection: CollectionName, query: str, k: int = 4):
        self.search_calls.append((collection, query, k))
        return list(self._search_results)


def _loader(paths: list[Path]) -> list[KnowledgeDocument]:
    _ = paths
    return [KnowledgeDocument(source="docs/a.md", content="A"), KnowledgeDocument(source="docs/b.md", content="B")]


def _splitter(documents: list[KnowledgeDocument], collection: CollectionName) -> list[KnowledgeChunk]:
    chunks: list[KnowledgeChunk] = []
    for index, doc in enumerate(documents):
        content_hash = ContentHash.from_text(doc.content)
        chunk_id = ChunkId.from_parts(
            collection=collection,
            source=doc.source,
            chunk_index=index,
            content_hash=content_hash,
        )
        chunks.append(
            KnowledgeChunk(
                id=chunk_id,
                collection=collection,
                source=doc.source,
                chunk_index=index,
                content=doc.content,
                content_sha256=content_hash,
                ingested_at="2026-01-01T00:00:00+00:00",
            )
        )
    return chunks


def test_ingest_markdown_is_idempotent_with_stable_chunk_ids() -> None:
    repository = InMemoryKnowledgeRepository()
    use_case = IngestMarkdown(repository=repository, loader=_loader, splitter=_splitter)
    collection = CollectionName("knowledge_default")

    first = use_case.execute(paths=[Path("docs")], collection=collection)
    second = use_case.execute(paths=[Path("docs")], collection=collection)

    assert first.files_processed == 2
    assert first.chunks_processed == 2
    assert first.records_in_collection == 2
    assert second.records_in_collection == 2


def test_delete_collection_clears_only_target_collection() -> None:
    repository = InMemoryKnowledgeRepository()
    target = CollectionName("knowledge_default")
    other = CollectionName("runbooks")

    chunk = _splitter(_loader([]), target)[0]
    repository.upsert_chunks([chunk, replace(chunk, collection=other, id=ChunkId("runbooks:docs/a.md:0:abc123def456"))])

    DeleteCollection(repository).execute(target)

    assert repository.count_chunks(target) == 0
    assert repository.count_chunks(other) == 1


def test_search_knowledge_delegates_to_repository() -> None:
    expected = [
        KnowledgeSearchResult(
            id="demo:docs/a.md:0:abc",
            content="hello",
            metadata={"source": "docs/a.md", "chunk_index": 0},
        )
    ]
    repository = InMemoryKnowledgeRepository(search_results=expected)
    collection = CollectionName("demo")

    results = SearchKnowledge(repository).execute(collection=collection, query="hello", k=3)

    assert results == expected
    assert repository.search_calls == [(collection, "hello", 3)]
