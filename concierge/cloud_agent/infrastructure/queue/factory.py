"""Factory that resolves a TaskQueue from configuration."""

from __future__ import annotations

from concierge.cloud_agent.application.queues import TaskQueue
from concierge.cloud_agent.infrastructure.queue.memory import InMemoryTaskQueue
from concierge.settings import CloudAgentQueueBackend, get_cloud_agent_settings


def get_task_queue() -> TaskQueue:
    """Return the configured TaskQueue instance."""
    settings = get_cloud_agent_settings()
    backend = settings.queue_backend

    if backend is CloudAgentQueueBackend.MEMORY:
        return InMemoryTaskQueue()

    if backend is CloudAgentQueueBackend.AZURE_STORAGE_QUEUE:
        from concierge.cloud_agent.infrastructure.queue.azure_storage_queue import AzureStorageQueueTaskQueue

        if not settings.azure_storage_connection_string:
            raise ValueError(
                "CLOUD_AGENT_AZURE_STORAGE_CONNECTION_STRING must be set when "
                "CLOUD_AGENT_QUEUE_BACKEND=azure-storage-queue."
            )
        return AzureStorageQueueTaskQueue(
            connection_string=settings.azure_storage_connection_string,
            queue_name=settings.queue_name,
            dlq_name=settings.dlq_name,
        )

    raise ValueError(f"Unhandled CloudAgentQueueBackend value: {backend!r}.")  # pragma: no cover
