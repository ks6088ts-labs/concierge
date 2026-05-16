"""Tests for cloud_agent memory queue."""

from __future__ import annotations

import uuid

import pytest

from concierge.cloud_agent.infrastructure.queue.memory import InMemoryTaskQueue


@pytest.mark.anyio
async def test_enqueue_and_dequeue() -> None:
    queue = InMemoryTaskQueue()
    task_id = uuid.uuid4()
    await queue.enqueue(task_id)
    msg = await queue.dequeue(visibility_timeout=60)
    assert msg is not None
    assert msg.task_id == task_id
    assert msg.dequeue_count == 1


@pytest.mark.anyio
async def test_dequeue_empty_returns_none() -> None:
    queue = InMemoryTaskQueue()
    msg = await queue.dequeue(visibility_timeout=60)
    assert msg is None


@pytest.mark.anyio
async def test_ack_removes_from_inflight() -> None:
    queue = InMemoryTaskQueue()
    task_id = uuid.uuid4()
    await queue.enqueue(task_id)
    msg = await queue.dequeue(visibility_timeout=60)
    assert msg is not None
    await queue.ack(msg)
    assert len(queue._in_flight) == 0


@pytest.mark.anyio
async def test_nack_with_requeue() -> None:
    queue = InMemoryTaskQueue()
    task_id = uuid.uuid4()
    await queue.enqueue(task_id)
    msg = await queue.dequeue(visibility_timeout=60)
    assert msg is not None
    await queue.nack(msg, requeue=True)
    # Should be back in queue
    msg2 = await queue.dequeue(visibility_timeout=60)
    assert msg2 is not None
    assert msg2.task_id == task_id


@pytest.mark.anyio
async def test_nack_without_requeue() -> None:
    queue = InMemoryTaskQueue()
    task_id = uuid.uuid4()
    await queue.enqueue(task_id)
    msg = await queue.dequeue(visibility_timeout=60)
    assert msg is not None
    await queue.nack(msg, requeue=False)
    msg2 = await queue.dequeue(visibility_timeout=60)
    assert msg2 is None


@pytest.mark.anyio
async def test_move_to_dlq() -> None:
    queue = InMemoryTaskQueue()
    task_id = uuid.uuid4()
    await queue.enqueue(task_id)
    msg = await queue.dequeue(visibility_timeout=60)
    assert msg is not None
    await queue.move_to_dlq(msg, reason="test reason")
    assert await queue.dlq_size() == 1
    assert await queue.size() == 0


@pytest.mark.anyio
async def test_size() -> None:
    queue = InMemoryTaskQueue()
    assert await queue.size() == 0
    for _ in range(3):
        await queue.enqueue(uuid.uuid4())
    assert await queue.size() == 3
