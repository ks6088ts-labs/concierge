from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from concierge.todo.domain.entities.task import Task
from concierge.todo.domain.value_objects import TaskStatus


class TaskRepository(Protocol):
    def create(self, task: Task) -> Task: ...

    def get(self, task_id: UUID) -> Task | None: ...

    def list(self, status: TaskStatus | None = None) -> Sequence[Task]: ...

    def update(self, task: Task) -> Task: ...

    def delete(self, task_id: UUID) -> bool: ...
