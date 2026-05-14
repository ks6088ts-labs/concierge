from __future__ import annotations

import uuid
from typing import Protocol

from concierge.todo.domain.entities import Task
from concierge.todo.domain.value_objects import TaskStatus


class TaskRepository(Protocol):
    def save(self, task: Task) -> Task: ...

    def find_by_id(self, task_id: uuid.UUID) -> Task | None: ...

    def find_all(self, status: TaskStatus | None = None) -> list[Task]: ...

    def delete(self, task_id: uuid.UUID) -> bool: ...
