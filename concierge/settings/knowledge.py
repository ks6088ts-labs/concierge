from __future__ import annotations

from enum import Enum
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class KnowledgeEmbeddingProvider(str, Enum):
    FOUNDRY = "foundry"
    FAKE = "fake"


class KnowledgeVectorBackend(str, Enum):
    PGVECTOR = "pgvector"


class KnowledgeTarget(str, Enum):
    DOCKER = "docker"
    AZURE = "azure"


class KnowledgeSettings(BaseSettings):
    embedding_provider: KnowledgeEmbeddingProvider = KnowledgeEmbeddingProvider.FOUNDRY
    embedding_model: str = "text-embedding-3-small"
    vector_size: int = 1536
    vector_backend: KnowledgeVectorBackend = KnowledgeVectorBackend.PGVECTOR
    default_collection: str = "knowledge_default"
    chunk_size: int = 1000
    chunk_overlap: int = 200

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="KNOWLEDGE_",
        extra="ignore",
    )


@lru_cache
def get_knowledge_settings() -> KnowledgeSettings:
    return KnowledgeSettings()
