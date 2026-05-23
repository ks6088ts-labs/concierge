from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from concierge.knowledge.application.repositories import KnowledgeRepository
from concierge.knowledge.domain.entities import KnowledgeChunk, KnowledgeDocument, KnowledgeSearchResult
from concierge.knowledge.domain.value_objects import CollectionName


class MarkdownLoader(Protocol):
    def __call__(self, paths: list[Path]) -> list[KnowledgeDocument]: ...


class ChunkSplitter(Protocol):
    def __call__(self, documents: list[KnowledgeDocument], collection: CollectionName) -> list[KnowledgeChunk]: ...


@dataclass(frozen=True)
class IngestMarkdownResult:
    files_processed: int
    chunks_processed: int
    records_in_collection: int


class IngestMarkdown:
    def __init__(self, repository: KnowledgeRepository, loader: MarkdownLoader, splitter: ChunkSplitter):
        self.repository = repository
        self.loader = loader
        self.splitter = splitter

    def execute(self, paths: list[Path], collection: CollectionName) -> IngestMarkdownResult:
        documents = self.loader(paths)
        chunks = self.splitter(documents, collection)
        if chunks:
            self.repository.upsert_chunks(chunks)
        total = self.repository.count_chunks(collection)
        return IngestMarkdownResult(
            files_processed=len(documents),
            chunks_processed=len(chunks),
            records_in_collection=total,
        )


@dataclass(frozen=True)
class DeleteCollectionResult:
    collection: str


class DeleteCollection:
    def __init__(self, repository: KnowledgeRepository):
        self.repository = repository

    def execute(self, collection: CollectionName) -> DeleteCollectionResult:
        self.repository.drop_collection(collection)
        return DeleteCollectionResult(collection=str(collection))


class SearchKnowledge:
    def __init__(self, repository: KnowledgeRepository):
        self.repository = repository

    def execute(self, collection: CollectionName, query: str, k: int = 4) -> list[KnowledgeSearchResult]:
        return self.repository.search(collection=collection, query=query, k=k)
