"""Factory that resolves a TaskRepository from configuration.

Configuration is centralised in CloudAgentSettings, which reads the
``CLOUD_AGENT_REPOSITORY_BACKEND`` and ``CLOUD_AGENT_TABLE_NAME``
environment variables.
"""

from __future__ import annotations

from functools import lru_cache

from concierge.cloud_agent.application.repositories import TaskRepository
from concierge.cloud_agent.infrastructure.persistence.memory import InMemoryTaskRepository
from concierge.settings import CloudAgentRepositoryBackend, get_cloud_agent_settings


def _build_postgres_engine():
    from sqlalchemy import create_engine

    from concierge.settings import get_postgres_settings

    url = get_postgres_settings().connection_string
    return create_engine(url, pool_pre_ping=True)


def _resolve_azure_credentials() -> tuple[str, str]:
    from concierge.settings import get_azure_postgres_settings

    settings = get_azure_postgres_settings()
    if settings.use_entra_auth:
        from azure.identity import DefaultAzureCredential

        token = DefaultAzureCredential().get_token(settings.entra_token_scope)
        if not settings.dbuser:
            raise ValueError("AZURE_DBUSER must be set when AZURE_USE_ENTRA_AUTH=true.")
        return settings.dbuser, token.token
    if not (settings.dbuser and settings.dbpassword):
        raise ValueError("AZURE_DBUSER and AZURE_DBPASSWORD must be set when AZURE_USE_ENTRA_AUTH=false.")
    return settings.dbuser, settings.dbpassword


def _build_azure_postgres_engine():
    from sqlalchemy import create_engine

    from concierge.settings import get_azure_postgres_settings

    azure_settings = get_azure_postgres_settings()
    if not azure_settings.dbhost or not azure_settings.dbname:
        raise ValueError("AZURE_DBHOST and AZURE_DBNAME must be set in the environment.")
    user, password = _resolve_azure_credentials()
    url = azure_settings.build_connection_string(password=password, user=user)
    return create_engine(url, pool_pre_ping=True)


@lru_cache(maxsize=2)
def _get_cached_engine(backend: CloudAgentRepositoryBackend):
    if backend is CloudAgentRepositoryBackend.POSTGRES:
        return _build_postgres_engine()
    if backend is CloudAgentRepositoryBackend.AZURE_POSTGRES:
        return _build_azure_postgres_engine()
    raise ValueError(f"Unknown backend: {backend!r}")  # pragma: no cover


def get_task_repository() -> TaskRepository:
    """Return the configured TaskRepository instance."""
    settings = get_cloud_agent_settings()
    backend = settings.repository_backend

    if backend is CloudAgentRepositoryBackend.MEMORY:
        return InMemoryTaskRepository()

    if backend in (CloudAgentRepositoryBackend.POSTGRES, CloudAgentRepositoryBackend.AZURE_POSTGRES):
        from concierge.cloud_agent.infrastructure.persistence.postgres import SqlAlchemyTaskRepository

        engine = _get_cached_engine(backend)
        return SqlAlchemyTaskRepository(engine, table_name=settings.table_name)

    raise ValueError(f"Unhandled CloudAgentRepositoryBackend value: {backend!r}.")  # pragma: no cover
