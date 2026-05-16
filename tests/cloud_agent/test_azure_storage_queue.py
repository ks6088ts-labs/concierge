"""Tests for AzureStorageQueueTaskQueue using unittest.mock stubs."""

from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest

from concierge.cloud_agent.application.queues import QueueMessage
from concierge.cloud_agent.infrastructure.queue.azure_storage_queue import AzureStorageQueueTaskQueue


def _make_queue(
    connection_string: str = "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;"
    "AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KlB4a5UsC8OA==;"
    "QueueEndpoint=http://127.0.0.1:10001/devstoreaccount1;",
) -> AzureStorageQueueTaskQueue:
    with patch("concierge.cloud_agent.infrastructure.queue.azure_storage_queue.QueueClient") as MockClient:
        mock_instance = MagicMock()
        MockClient.from_connection_string.return_value = mock_instance
        queue = AzureStorageQueueTaskQueue(
            connection_string=connection_string,
            queue_name="test-queue",
            dlq_name="test-dlq",
        )
        queue._queue_client = mock_instance
        queue._dlq_client = MagicMock()
    return queue


@pytest.mark.anyio
async def test_enqueue_sends_message() -> None:
    queue = _make_queue()
    task_id = uuid.uuid4()
    await queue.enqueue(task_id)
    queue._queue_client.send_message.assert_called_once()
    call_args = queue._queue_client.send_message.call_args[0][0]
    body = json.loads(call_args)
    assert body["task_id"] == str(task_id)


@pytest.mark.anyio
async def test_dequeue_returns_message() -> None:
    queue = _make_queue()
    task_id = uuid.uuid4()
    mock_msg = MagicMock()
    mock_msg.content = json.dumps({"task_id": str(task_id)})
    mock_msg.id = "msg-id-1"
    mock_msg.pop_receipt = "pop-receipt-1"
    mock_msg.dequeue_count = 1
    queue._queue_client.receive_messages.return_value = [mock_msg]

    msg = await queue.dequeue(visibility_timeout=60)
    assert msg is not None
    assert msg.task_id == task_id
    assert msg.receipt == "msg-id-1:pop-receipt-1"


@pytest.mark.anyio
async def test_dequeue_empty_returns_none() -> None:
    queue = _make_queue()
    queue._queue_client.receive_messages.return_value = []
    msg = await queue.dequeue(visibility_timeout=60)
    assert msg is None


@pytest.mark.anyio
async def test_ack_deletes_message() -> None:
    queue = _make_queue()
    msg = QueueMessage(task_id=uuid.uuid4(), receipt="mid:pop", dequeue_count=1)
    await queue.ack(msg)
    queue._queue_client.delete_message.assert_called_once_with("mid", "pop")


@pytest.mark.anyio
async def test_nack_with_requeue() -> None:
    queue = _make_queue()
    msg = QueueMessage(task_id=uuid.uuid4(), receipt="mid:pop", dequeue_count=1)
    await queue.nack(msg, requeue=True)
    queue._queue_client.update_message.assert_called_once_with("mid", "pop", visibility_timeout=0)


@pytest.mark.anyio
async def test_nack_without_requeue() -> None:
    queue = _make_queue()
    msg = QueueMessage(task_id=uuid.uuid4(), receipt="mid:pop", dequeue_count=1)
    await queue.nack(msg, requeue=False)
    queue._queue_client.delete_message.assert_called_once_with("mid", "pop")


@pytest.mark.anyio
async def test_move_to_dlq() -> None:
    queue = _make_queue()
    task_id = uuid.uuid4()
    msg = QueueMessage(task_id=task_id, receipt="mid:pop", dequeue_count=1)
    await queue.move_to_dlq(msg, reason="test")
    queue._dlq_client.send_message.assert_called_once()
    queue._queue_client.delete_message.assert_called_once_with("mid", "pop")
