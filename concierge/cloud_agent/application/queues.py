from __future__ import annotations

import uuid
from typing import Protocol

from pydantic import BaseModel


class QueueMessage(BaseModel):
    task_id: uuid.UUID
    receipt: str  # implementation-specific ack/nack handle
    dequeue_count: int


class TaskQueue(Protocol):
    async def enqueue(self, task_id: uuid.UUID) -> None: ...

    async def dequeue(self, *, visibility_timeout: int) -> QueueMessage | None: ...

    async def ack(self, message: QueueMessage) -> None: ...

    async def nack(self, message: QueueMessage, *, requeue: bool) -> None: ...

    async def move_to_dlq(self, message: QueueMessage, *, reason: str) -> None: ...

    async def dlq_size(self) -> int: ...

    async def size(self) -> int: ...
