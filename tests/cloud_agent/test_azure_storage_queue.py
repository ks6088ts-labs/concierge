"""Tests for AzureStorageQueueTaskQueue using unittest.mock stubs."""

from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest
from azure.core.exceptions import ResourceExistsError

from concierge.cloud_agent.application.queues import QueueMessage
from concierge.cloud_agent.infrastructure.queue.azure_storage_queue import AzureStorageQueueTaskQueue


def _make_queue(
    account_url: str = "https://devstoreaccount1.queue.core.windows.net",
) -> tuple[AzureStorageQueueTaskQueue, MagicMock, MagicMock]:
    mock_queue_client = MagicMock()
    mock_dlq_client = MagicMock()

    def _client_factory(*_args, queue_name: str, **_kwargs):
        return mock_queue_client if queue_name == "test-queue" else mock_dlq_client

    with patch(
        "concierge.cloud_agent.infrastructure.queue.azure_storage_queue.QueueClient",
        side_effect=_client_factory,
    ):
        queue = AzureStorageQueueTaskQueue(
            account_url=account_url,
            queue_name="test-queue",
            dlq_name="test-dlq",
            credential=MagicMock(),
        )
    return queue, mock_queue_client, mock_dlq_client


def test_constructor_requires_account_url() -> None:
    with pytest.raises(ValueError, match="account_url"):
        AzureStorageQueueTaskQueue(
            account_url="",
            queue_name="q",
            dlq_name="dlq",
            credential=MagicMock(),
        )


def test_constructor_is_idempotent_when_queue_already_exists() -> None:
    """Existing queues must not cause AzureStorageQueueTaskQueue to fail.

    The Azure Storage SDK raises ``ResourceExistsError`` from ``create_queue``
    when the queue already exists; the constructor must swallow it so that
    repeated startups remain idempotent.
    """
    mock_queue_client = MagicMock()
    mock_dlq_client = MagicMock()
    mock_queue_client.create_queue.side_effect = ResourceExistsError("queue exists")
    mock_dlq_client.create_queue.side_effect = ResourceExistsError("dlq exists")

    def _client_factory(*_args, queue_name: str, **_kwargs):
        return mock_queue_client if queue_name == "test-queue" else mock_dlq_client

    with patch(
        "concierge.cloud_agent.infrastructure.queue.azure_storage_queue.QueueClient",
        side_effect=_client_factory,
    ):
        AzureStorageQueueTaskQueue(
            account_url="https://devstoreaccount1.queue.core.windows.net",
            queue_name="test-queue",
            dlq_name="test-dlq",
            credential=MagicMock(),
        )

    mock_queue_client.create_queue.assert_called_once()
    mock_dlq_client.create_queue.assert_called_once()


@pytest.mark.anyio
async def test_enqueue_sends_message() -> None:
    queue, mock_client, _ = _make_queue()
    task_id = uuid.uuid4()
    await queue.enqueue(task_id)
    mock_client.send_message.assert_called_once()
    call_args = mock_client.send_message.call_args[0][0]
    body = json.loads(call_args)
    assert body["task_id"] == str(task_id)


@pytest.mark.anyio
async def test_dequeue_returns_message() -> None:
    queue, mock_client, _ = _make_queue()
    task_id = uuid.uuid4()
    mock_msg = MagicMock()
    mock_msg.content = json.dumps({"task_id": str(task_id)})
    mock_msg.id = "msg-id-1"
    mock_msg.pop_receipt = "pop-receipt-1"
    mock_msg.dequeue_count = 1
    mock_client.receive_messages.return_value = [mock_msg]

    msg = await queue.dequeue(visibility_timeout=60)
    assert msg is not None
    assert msg.task_id == task_id
    assert msg.receipt == "msg-id-1:pop-receipt-1"


@pytest.mark.anyio
async def test_dequeue_empty_returns_none() -> None:
    queue, mock_client, _ = _make_queue()
    mock_client.receive_messages.return_value = []
    msg = await queue.dequeue(visibility_timeout=60)
    assert msg is None


@pytest.mark.anyio
async def test_ack_deletes_message() -> None:
    queue, mock_client, _ = _make_queue()
    msg = QueueMessage(task_id=uuid.uuid4(), receipt="mid:pop", dequeue_count=1)
    await queue.ack(msg)
    mock_client.delete_message.assert_called_once_with("mid", "pop")


@pytest.mark.anyio
async def test_nack_with_requeue() -> None:
    queue, mock_client, _ = _make_queue()
    msg = QueueMessage(task_id=uuid.uuid4(), receipt="mid:pop", dequeue_count=1)
    await queue.nack(msg, requeue=True)
    mock_client.update_message.assert_called_once_with("mid", "pop", visibility_timeout=0)


@pytest.mark.anyio
async def test_nack_without_requeue() -> None:
    queue, mock_client, _ = _make_queue()
    msg = QueueMessage(task_id=uuid.uuid4(), receipt="mid:pop", dequeue_count=1)
    await queue.nack(msg, requeue=False)
    mock_client.delete_message.assert_called_once_with("mid", "pop")


@pytest.mark.anyio
async def test_move_to_dlq() -> None:
    queue, mock_client, mock_dlq = _make_queue()
    task_id = uuid.uuid4()
    msg = QueueMessage(task_id=task_id, receipt="mid:pop", dequeue_count=1)
    await queue.move_to_dlq(msg, reason="test")
    mock_dlq.send_message.assert_called_once()
    mock_client.delete_message.assert_called_once_with("mid", "pop")
