from __future__ import annotations

import importlib
from datetime import datetime, timezone
from pathlib import Path

from concierge.knowledge.domain.entities import KnowledgeChunk, KnowledgeDocument
from concierge.knowledge.domain.value_objects import ChunkId, CollectionName, ContentHash
from concierge.settings import get_knowledge_settings


def _resolve_markdown_files(paths: list[Path]) -> list[Path]:
    files: set[Path] = set()
    for path in paths:
        if path.is_file() and path.suffix.lower() == ".md":
            files.add(path)
        elif path.is_dir():
            files.update(candidate for candidate in path.rglob("*.md") if candidate.is_file())
    return sorted(files)


def load_markdown_documents(paths: list[Path]) -> list[KnowledgeDocument]:
    docs: list[KnowledgeDocument] = []
    workspace = Path.cwd()
    for file in _resolve_markdown_files(paths):
        try:
            source = str(file.resolve().relative_to(workspace.resolve()))
        except ValueError:
            source = str(file.resolve())
        docs.append(KnowledgeDocument(source=source, content=file.read_text(encoding="utf-8")))
    return docs


def split_documents(documents: list[KnowledgeDocument], collection: CollectionName) -> list[KnowledgeChunk]:
    settings = get_knowledge_settings()
    splitter_cls = getattr(
        importlib.import_module("langchain_text_splitters"),
        "RecursiveCharacterTextSplitter",
    )
    splitter = splitter_cls(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    ingested_at = datetime.now(timezone.utc).isoformat()
    chunks: list[KnowledgeChunk] = []
    for document in documents:
        for chunk_index, chunk_text in enumerate(splitter.split_text(document.content)):
            content_hash = ContentHash.from_text(chunk_text)
            chunk_id = ChunkId.from_parts(
                collection=collection,
                source=document.source,
                chunk_index=chunk_index,
                content_hash=content_hash,
            )
            chunks.append(
                KnowledgeChunk(
                    id=chunk_id,
                    collection=collection,
                    source=document.source,
                    chunk_index=chunk_index,
                    content=chunk_text,
                    content_sha256=content_hash,
                    ingested_at=ingested_at,
                )
            )
    return chunks
