from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy import create_engine, inspect, text

from concierge.knowledge.domain.entities import KnowledgeChunk, KnowledgeSearchResult
from concierge.knowledge.domain.value_objects import CollectionName
from concierge.settings import KnowledgeTarget, get_azure_postgres_settings, get_postgres_settings


@dataclass
class PgVectorKnowledgeRepository:
    store: object | None
    collection: CollectionName
    connection_url: str

    def upsert_chunks(self, chunks: list[KnowledgeChunk]) -> int:
        if not chunks:
            return 0
        if self.store is None:  # pragma: no cover - guarded by factory usage
            raise ValueError("Vector store is not configured for write operations.")
        from langchain_core.documents import Document

        documents = [Document(page_content=chunk.content, metadata=chunk.metadata) for chunk in chunks]
        ids = [str(chunk.id) for chunk in chunks]
        store = cast(Any, self.store)
        store.add_documents(documents=documents, ids=ids)
        return len(chunks)

    def count_chunks(self, collection: CollectionName) -> int:
        engine = create_engine(self.connection_url, pool_pre_ping=True)
        try:
            with engine.connect() as connection:
                result = connection.execute(text(f'SELECT COUNT(*) FROM "{collection.value}"'))
                return int(result.scalar_one())
        except Exception:
            return 0
        finally:
            engine.dispose()

    def drop_collection(self, collection: CollectionName) -> None:
        from langchain_postgres import PGEngine

        engine = PGEngine.from_connection_string(url=self.connection_url)
        engine.drop_table(table_name=collection.value)

    def search(self, collection: CollectionName, query: str, k: int = 4) -> list[KnowledgeSearchResult]:
        _ = collection
        if self.store is None:
            return []
        store = cast(Any, self.store)
        docs = cast(list[Any], store.similarity_search(query=query, k=k))
        return [
            KnowledgeSearchResult(
                id=str(doc.id) if doc.id else "",
                content=doc.page_content,
                metadata=dict(doc.metadata),
            )
            for doc in docs
        ]


def _resolve_azure_credentials() -> tuple[str, str]:
    settings = get_azure_postgres_settings()
    if settings.use_entra_auth:
        from azure.identity import DefaultAzureCredential

        token = DefaultAzureCredential().get_token(settings.entra_token_scope)
        if not settings.dbuser:
            raise ValueError(
                "AZURE_DBUSER must be set to the Entra principal name (or PostgreSQL role) "
                "when AZURE_USE_ENTRA_AUTH=true."
            )
        return settings.dbuser, token.token
    if not (settings.dbuser and settings.dbpassword):
        raise ValueError("AZURE_DBUSER and AZURE_DBPASSWORD must be set when AZURE_USE_ENTRA_AUTH=false.")
    return settings.dbuser, settings.dbpassword


def build_connection_url(target: KnowledgeTarget) -> str:
    if target is KnowledgeTarget.DOCKER:
        return get_postgres_settings().connection_string

    settings = get_azure_postgres_settings()
    if not settings.dbhost or not settings.dbname:
        raise ValueError("AZURE_DBHOST and AZURE_DBNAME must be set.")
    user, password = _resolve_azure_credentials()
    return settings.build_connection_string(password=password, user=user)


def _table_exists(connection_url: str, table_name: str) -> bool:
    engine = create_engine(connection_url, pool_pre_ping=True)
    try:
        return inspect(engine).has_table(table_name)
    finally:
        engine.dispose()


def create_pgvector_repository(
    *,
    collection: CollectionName,
    target: KnowledgeTarget,
    embeddings: object | None,
    vector_size: int,
    ensure_collection: bool = False,
) -> PgVectorKnowledgeRepository:
    from langchain_postgres import Column, PGEngine, PGVectorStore

    connection_url = build_connection_url(target)
    engine = PGEngine.from_connection_string(url=connection_url)
    if ensure_collection and not _table_exists(connection_url, collection.value):
        engine.init_vectorstore_table(
            table_name=collection.value,
            vector_size=vector_size,
            id_column=Column("langchain_id", "TEXT", nullable=False),
            overwrite_existing=False,
        )
    store = None
    if embeddings is not None:
        from langchain_core.embeddings import Embeddings

        store = PGVectorStore.create_sync(
            engine=engine,
            table_name=collection.value,
            embedding_service=cast(Embeddings, embeddings),
        )
    return PgVectorKnowledgeRepository(store=store, collection=collection, connection_url=connection_url)
