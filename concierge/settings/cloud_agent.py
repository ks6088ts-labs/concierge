"""Settings for the Cloud Agent application.

All Cloud Agent-related environment variables are aggregated here so the
rest of the codebase never has to call ``os.environ`` directly.
Variables are read with a ``CLOUD_AGENT_`` prefix, e.g.
``CLOUD_AGENT_REPOSITORY_BACKEND`` and ``CLOUD_AGENT_QUEUE_BACKEND``.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class CloudAgentRepositoryBackend(str, Enum):
    """Supported persistence backends for the Cloud Agent application."""

    MEMORY = "memory"
    POSTGRES = "postgres"
    AZURE_POSTGRES = "azure-postgres"


class CloudAgentQueueBackend(str, Enum):
    """Supported queue backends for the Cloud Agent application."""

    MEMORY = "memory"
    AZURE_STORAGE_QUEUE = "azure-storage-queue"


class CloudAgentSettings(BaseSettings):
    """Aggregated configuration for the Cloud Agent application.

    Attributes:
        repository_backend: Which persistence backend to use.
        table_name: Table name for SQL backends.
        queue_backend: Which queue backend to use.
        queue_name: Queue name for the main task queue.
        dlq_name: Queue name for the dead letter queue.
        azure_storage_account_url: Azure Storage queue service endpoint
            (e.g. ``https://<account>.queue.core.windows.net``). Authentication
            is performed exclusively via Microsoft Entra ID
            (``DefaultAzureCredential``); connection strings are not supported.
        visibility_timeout_seconds: Queue message visibility timeout.
        max_retries: Default maximum retry count for tasks.
        worker_concurrency: Number of concurrent task processors per worker.
        poll_interval_seconds: Polling interval when queue is empty.
    """

    repository_backend: CloudAgentRepositoryBackend = CloudAgentRepositoryBackend.MEMORY
    table_name: str = "cloud_agent_tasks"
    queue_backend: CloudAgentQueueBackend = CloudAgentQueueBackend.MEMORY
    queue_name: str = "cloud-agent-tasks"
    dlq_name: str = "cloud-agent-dlq"
    azure_storage_account_url: str = ""
    visibility_timeout_seconds: int = 60
    max_retries: int = 3
    worker_concurrency: int = 1
    poll_interval_seconds: float = 1.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="CLOUD_AGENT_",
        extra="ignore",
    )


@lru_cache
def get_cloud_agent_settings() -> CloudAgentSettings:
    return CloudAgentSettings()
