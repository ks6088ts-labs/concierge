"""Factory that resolves a ``TaskRepository`` from the environment.

The backend is selected by the ``TODO_REPOSITORY_BACKEND`` environment
variable:

* ``memory`` (default) — in-process ``InMemoryTaskRepository``
* ``postgres`` — ``SqlAlchemyTaskRepository`` backed by the local Docker
  Compose PostgreSQL service (``POSTGRES_*`` variables)
* ``azure-postgres`` — ``SqlAlchemyTaskRepository`` backed by Azure Database
  for PostgreSQL Flexible Server (``AZURE_*`` variables)

When ``TODO_REPOSITORY_BACKEND=azure-postgres`` and
``AZURE_USE_ENTRA_AUTH=true``, a Microsoft Entra access token is obtained via
``DefaultAzureCredential`` and used as the database password (matching the
pattern in ``scripts/postgresql/vanilla.py``).
"""

from __future__ import annotations

import os
from functools import lru_cache

from concierge.todo.application.repositories import TaskRepository
from concierge.todo.infrastructure.persistence.memory import InMemoryTaskRepository

_BACKEND_ENV = "TODO_REPOSITORY_BACKEND"
_TABLE_NAME_ENV = "TODO_TABLE_NAME"
_DEFAULT_TABLE_NAME = "todo_tasks"

# Valid backend values.
BACKEND_MEMORY = "memory"
BACKEND_POSTGRES = "postgres"
BACKEND_AZURE_POSTGRES = "azure-postgres"


def _get_table_name() -> str:
    return os.environ.get(_TABLE_NAME_ENV, _DEFAULT_TABLE_NAME)


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


@lru_cache(maxsize=1)
def _get_cached_engine(backend: str):
    """Build (and cache per backend value) the SQLAlchemy engine."""
    if backend == BACKEND_POSTGRES:
        return _build_postgres_engine()
    if backend == BACKEND_AZURE_POSTGRES:
        return _build_azure_postgres_engine()
    raise ValueError(f"Unknown backend: {backend!r}")  # pragma: no cover


def get_task_repository() -> TaskRepository:
    """Return the configured ``TaskRepository`` instance.

    The backend is controlled by ``TODO_REPOSITORY_BACKEND`` (default:
    ``memory``). This function is safe to call from both FastAPI
    dependencies and the Typer CLI.
    """
    backend = os.environ.get(_BACKEND_ENV, BACKEND_MEMORY).strip().lower()

    if backend == BACKEND_MEMORY:
        return InMemoryTaskRepository()

    if backend in (BACKEND_POSTGRES, BACKEND_AZURE_POSTGRES):
        from concierge.todo.infrastructure.persistence.postgres import SqlAlchemyTaskRepository

        engine = _get_cached_engine(backend)
        return SqlAlchemyTaskRepository(engine, table_name=_get_table_name())

    raise ValueError(
        f"Unknown TODO_REPOSITORY_BACKEND={backend!r}. "
        f"Valid values: {BACKEND_MEMORY!r}, {BACKEND_POSTGRES!r}, {BACKEND_AZURE_POSTGRES!r}."
    )
