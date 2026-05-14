"""Settings for the Todo application.

All Todo-related environment variables are aggregated here so the rest of
the codebase never has to call ``os.environ`` directly. Variables are read
with a ``TODO_`` prefix, e.g. ``TODO_REPOSITORY_BACKEND`` and
``TODO_TABLE_NAME``.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class TodoRepositoryBackend(str, Enum):
    """Supported persistence backends for the Todo application.

    Using an enum (instead of free-form strings) ensures that invalid
    backend values are rejected at configuration load time.
    """

    MEMORY = "memory"
    POSTGRES = "postgres"
    AZURE_POSTGRES = "azure-postgres"


class TodoSettings(BaseSettings):
    """Aggregated configuration for the Todo application.

    Attributes:
        repository_backend: Which persistence backend to use. One of
            ``memory``, ``postgres``, or ``azure-postgres``.
        table_name: Table name for SQL backends (ignored by ``memory``).
    """

    repository_backend: TodoRepositoryBackend = TodoRepositoryBackend.MEMORY
    table_name: str = "todo_tasks"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="TODO_",
        extra="ignore",
    )


@lru_cache
def get_todo_settings() -> TodoSettings:
    return TodoSettings()
