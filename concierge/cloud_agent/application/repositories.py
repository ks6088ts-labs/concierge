from __future__ import annotations

import uuid
from typing import Protocol

from concierge.cloud_agent.domain.entities import Task
from concierge.cloud_agent.domain.value_objects import TaskStatus


class TaskRepository(Protocol):
    def save(self, task: Task) -> Task: ...

    def find_by_id(self, task_id: uuid.UUID) -> Task | None: ...

    def find_all(
        self,
        status: TaskStatus | None = None,
        agent_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Task]: ...

    def delete(self, task_id: uuid.UUID) -> bool: ...

    def count(
        self,
        status: TaskStatus | None = None,
        agent_type: str | None = None,
    ) -> int: ...
