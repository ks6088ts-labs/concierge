"""Factory that resolves a ``TaskRepository`` from configuration.

Configuration is centralised in :class:`concierge.settings.TodoSettings`,
which reads the ``TODO_REPOSITORY_BACKEND`` and ``TODO_TABLE_NAME``
environment variables. Supported backends are declared in the
:class:`concierge.settings.TodoRepositoryBackend` enum:

* :attr:`~concierge.settings.TodoRepositoryBackend.MEMORY` (default) —
  in-process :class:`InMemoryTaskRepository`.
* :attr:`~concierge.settings.TodoRepositoryBackend.POSTGRES` —
  :class:`SqlAlchemyTaskRepository` backed by the local Docker Compose
  PostgreSQL service (``POSTGRES_*`` variables).
* :attr:`~concierge.settings.TodoRepositoryBackend.AZURE_POSTGRES` —
  :class:`SqlAlchemyTaskRepository` backed by Azure Database for PostgreSQL
  Flexible Server (``AZURE_*`` variables).

When ``TODO_REPOSITORY_BACKEND=azure-postgres`` and
``AZURE_USE_ENTRA_AUTH=true``, a Microsoft Entra access token is obtained via
``DefaultAzureCredential`` and used as the database password (matching the
pattern in ``scripts/postgresql/vanilla.py``).
"""

from __future__ import annotations

from functools import lru_cache

from concierge.settings import TodoRepositoryBackend, get_todo_settings
from concierge.todo.application.repositories import TaskRepository
from concierge.todo.infrastructure.persistence.memory import InMemoryTaskRepository


def _build_postgres_engine():
    """Build a SQLAlchemy Engine for the local Docker Compose PostgreSQL."""
    from sqlalchemy import create_engine

    from concierge.settings import get_postgres_settings

    url = get_postgres_settings().connection_string
    return create_engine(url, pool_pre_ping=True)


def _resolve_azure_credentials() -> tuple[str, str]:
    """Return ``(user, password)`` for the Azure PostgreSQL connection.

    Mirrors the same function in ``scripts/postgresql/vanilla.py``.
    """
    from concierge.settings import get_azure_postgres_settings

    settings = get_azure_postgres_settings()
    if settings.use_entra_auth:
        from azure.identity import DefaultAzureCredential

        token = DefaultAzureCredential().get_token(settings.entra_token_scope)
        if not settings.dbuser:
            raise ValueError(
                "AZURE_DBUSER must be set to the Entra principal name (or PostgreSQL "
                "role mapped to that principal) when AZURE_USE_ENTRA_AUTH=true."
            )
        return settings.dbuser, token.token
    if not (settings.dbuser and settings.dbpassword):
        raise ValueError("AZURE_DBUSER and AZURE_DBPASSWORD must be set when AZURE_USE_ENTRA_AUTH=false.")
    return settings.dbuser, settings.dbpassword


def _build_azure_postgres_engine():
    """Build a SQLAlchemy Engine for Azure Database for PostgreSQL.

    For Entra ID authentication, a fresh token is fetched each time the
    engine is (re-)created. Because Entra tokens expire, callers that need
    long-lived connections should recreate the engine periodically; for the
    typical short-lived CLI / request lifecycle this is not an issue.
    """
    from sqlalchemy import create_engine

    from concierge.settings import get_azure_postgres_settings

    azure_settings = get_azure_postgres_settings()
    if not azure_settings.dbhost or not azure_settings.dbname:
        raise ValueError(
            "AZURE_DBHOST and AZURE_DBNAME must be set in the environment (.env). "
            "See .env.template for the required Azure PostgreSQL variables."
        )
    user, password = _resolve_azure_credentials()
    url = azure_settings.build_connection_string(password=password, user=user)
    return create_engine(url, pool_pre_ping=True)


@lru_cache(maxsize=2)
def _get_cached_engine(backend: TodoRepositoryBackend):
    """Build (and cache per backend value) the SQLAlchemy engine."""
    if backend is TodoRepositoryBackend.POSTGRES:
        return _build_postgres_engine()
    if backend is TodoRepositoryBackend.AZURE_POSTGRES:
        return _build_azure_postgres_engine()
    raise ValueError(f"Unknown backend: {backend!r}")  # pragma: no cover


def get_task_repository() -> TaskRepository:
    """Return the configured ``TaskRepository`` instance.

    The backend is controlled by ``TODO_REPOSITORY_BACKEND`` (default:
    ``memory``). This function is safe to call from both FastAPI
    dependencies and the Typer CLI.
    """
    settings = get_todo_settings()
    backend = settings.repository_backend

    if backend is TodoRepositoryBackend.MEMORY:
        return InMemoryTaskRepository()

    if backend in (TodoRepositoryBackend.POSTGRES, TodoRepositoryBackend.AZURE_POSTGRES):
        from concierge.todo.infrastructure.persistence.postgres import SqlAlchemyTaskRepository

        engine = _get_cached_engine(backend)
        return SqlAlchemyTaskRepository(engine, table_name=settings.table_name)

    # ``repository_backend`` is enum-typed, so this branch is unreachable
    # in practice; it stays as a defensive guard in case the enum is
    # extended without updating this function.
    raise ValueError(  # pragma: no cover
        f"Unhandled TodoRepositoryBackend value: {backend!r}."
    )
