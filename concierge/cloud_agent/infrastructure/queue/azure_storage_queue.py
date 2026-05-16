"""Azure Storage Queue-based task queue implementation.

Uses the ``azure-storage-queue`` SDK. Authentication is performed exclusively
via Microsoft Entra ID using ``DefaultAzureCredential``; account keys and
connection strings are intentionally not supported.

The DLQ is a separate queue with the name configured via
``CLOUD_AGENT_DLQ_NAME``.
"""

from __future__ import annotations

import base64
import json
import uuid

from azure.core.credentials import TokenCredential
from azure.core.exceptions import ResourceExistsError
from azure.identity import DefaultAzureCredential
from azure.storage.queue import QueueClient

from concierge.cloud_agent.application.queues import QueueMessage
from concierge.loggers import get_logger

logger = get_logger("concierge.cloud_agent.queue.azure_storage_queue")


def _ensure_queue_exists(client: QueueClient) -> None:
    """Create the queue if it doesn't exist yet (idempotent)."""
    try:
        client.create_queue()
    except ResourceExistsError:
        logger.debug("Queue %r already exists; skipping creation.", client.queue_name)


class AzureStorageQueueTaskQueue:
    """TaskQueue backed by Azure Storage Queue with Entra ID authentication.

    Args:
        account_url: Azure Storage queue service endpoint
            (e.g. ``https://<account>.queue.core.windows.net``).
        queue_name: Main task queue name.
        dlq_name: Dead letter queue name.
        credential: Token credential used to authenticate every request.
            Defaults to :class:`azure.identity.DefaultAzureCredential`, which
            resolves Entra ID identities from the environment (``az login``,
            managed identity, workload identity, etc.).
    """

    def __init__(
        self,
        account_url: str,
        queue_name: str,
        dlq_name: str,
        credential: TokenCredential | None = None,
    ) -> None:
        if not account_url:
            raise ValueError("account_url must be a non-empty Azure Storage queue service endpoint.")
        self._credential: TokenCredential = credential or DefaultAzureCredential()
        self._queue_client = QueueClient(
            account_url=account_url,
            queue_name=queue_name,
            credential=self._credential,
        )
        self._dlq_client = QueueClient(
            account_url=account_url,
            queue_name=dlq_name,
            credential=self._credential,
        )
        _ensure_queue_exists(self._queue_client)
        _ensure_queue_exists(self._dlq_client)

    async def enqueue(self, task_id: uuid.UUID) -> None:
        message = json.dumps({"task_id": str(task_id)})
        self._queue_client.send_message(message)

    async def dequeue(self, *, visibility_timeout: int = 60) -> QueueMessage | None:
        messages = self._queue_client.receive_messages(max_messages=1, visibility_timeout=visibility_timeout)
        for msg in messages:
            try:
                body_bytes = base64.b64decode(msg.content)
                body = json.loads(body_bytes)
            except Exception:
                body = json.loads(msg.content)
            task_id = uuid.UUID(body["task_id"])
            return QueueMessage(
                task_id=task_id,
                receipt=f"{msg.id}:{msg.pop_receipt}",
                dequeue_count=msg.dequeue_count or 1,
            )
        return None

    async def ack(self, message: QueueMessage) -> None:
        msg_id, pop_receipt = message.receipt.split(":", 1)
        self._queue_client.delete_message(msg_id, pop_receipt)

    async def nack(self, message: QueueMessage, *, requeue: bool) -> None:
        if requeue:
            # Make the message immediately visible again by updating visibility to 0
            msg_id, pop_receipt = message.receipt.split(":", 1)
            self._queue_client.update_message(msg_id, pop_receipt, visibility_timeout=0)
        else:
            msg_id, pop_receipt = message.receipt.split(":", 1)
            self._queue_client.delete_message(msg_id, pop_receipt)

    async def move_to_dlq(self, message: QueueMessage, *, reason: str) -> None:
        dlq_body = json.dumps({"task_id": str(message.task_id), "reason": reason})
        self._dlq_client.send_message(dlq_body)
        msg_id, pop_receipt = message.receipt.split(":", 1)
        self._queue_client.delete_message(msg_id, pop_receipt)

    async def dlq_size(self) -> int:
        props = self._dlq_client.get_queue_properties()
        return props.approximate_message_count or 0

    async def size(self) -> int:
        props = self._queue_client.get_queue_properties()
        return props.approximate_message_count or 0
