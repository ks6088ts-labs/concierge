"""In-memory task queue implementation using asyncio.Queue.

Suitable for local development and testing. Does not persist across
process restarts. Implements visibility timeout via soft state tracking.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from concierge.cloud_agent.application.queues import QueueMessage


class InMemoryTaskQueue:
    """In-process asyncio-based task queue with basic visibility simulation."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[uuid.UUID] = asyncio.Queue()
        self._dlq: list[dict[str, Any]] = []
        # receipt -> (task_id, visible_at, dequeue_count)
        self._in_flight: dict[str, tuple[uuid.UUID, datetime, int]] = {}
        self._receipt_counter = 0

    def _next_receipt(self) -> str:
        self._receipt_counter += 1
        return str(self._receipt_counter)

    async def enqueue(self, task_id: uuid.UUID) -> None:
        await self._queue.put(task_id)

    async def dequeue(self, *, visibility_timeout: int = 60) -> QueueMessage | None:
        # Re-check expired in-flight items first
        now = datetime.now(timezone.utc)
        expired_receipts = [receipt for receipt, (tid, visible_at, _) in self._in_flight.items() if now >= visible_at]
        for receipt in expired_receipts:
            tid, _, count = self._in_flight.pop(receipt)
            await self._queue.put(tid)

        try:
            task_id = self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

        receipt = self._next_receipt()
        dequeue_count = 1
        visible_at = datetime.now(timezone.utc) + timedelta(seconds=visibility_timeout)
        self._in_flight[receipt] = (task_id, visible_at, dequeue_count)
        return QueueMessage(task_id=task_id, receipt=receipt, dequeue_count=dequeue_count)

    async def ack(self, message: QueueMessage) -> None:
        self._in_flight.pop(message.receipt, None)
        try:
            self._queue.task_done()
        except ValueError:
            pass

    async def nack(self, message: QueueMessage, *, requeue: bool) -> None:
        self._in_flight.pop(message.receipt, None)
        if requeue:
            await self._queue.put(message.task_id)

    async def move_to_dlq(self, message: QueueMessage, *, reason: str) -> None:
        self._in_flight.pop(message.receipt, None)
        self._dlq.append({"task_id": message.task_id, "reason": reason})

    async def dlq_size(self) -> int:
        return len(self._dlq)

    async def size(self) -> int:
        return self._queue.qsize()
