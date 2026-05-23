from __future__ import annotations

from azure.identity import DefaultAzureCredential
from langchain_core.embeddings import DeterministicFakeEmbedding, Embeddings

from concierge.settings import KnowledgeEmbeddingProvider, get_knowledge_settings, get_microsoft_foundry_settings


def _resource_openai_v1_endpoint() -> str:
    project_endpoint = get_microsoft_foundry_settings().azure_ai_project_endpoint
    resource = project_endpoint.split("/api/projects/", 1)[0]
    return f"{resource}/openai/v1"


def create_embeddings() -> Embeddings:
    settings = get_knowledge_settings()
    if settings.embedding_provider is KnowledgeEmbeddingProvider.FAKE:
        return DeterministicFakeEmbedding(size=settings.vector_size)

    from langchain.embeddings import init_embeddings

    return init_embeddings(
        f"azure_ai:{settings.embedding_model}",
        endpoint=_resource_openai_v1_endpoint(),
        credential=DefaultAzureCredential(),
        api_version="preview",
    )
