from __future__ import annotations

import copy
import uuid

from concierge.cloud_agent.domain.entities import Task
from concierge.cloud_agent.domain.value_objects import TaskStatus


class InMemoryTaskRepository:
    def __init__(self) -> None:
        self._tasks: dict[uuid.UUID, Task] = {}

    def save(self, task: Task) -> Task:
        self._tasks[task.id] = copy.deepcopy(task)
        return copy.deepcopy(self._tasks[task.id])

    def find_by_id(self, task_id: uuid.UUID) -> Task | None:
        task = self._tasks.get(task_id)
        return copy.deepcopy(task) if task is not None else None

    def find_all(
        self,
        status: TaskStatus | None = None,
        agent_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Task]:
        tasks = list(self._tasks.values())
        if status is not None:
            tasks = [t for t in tasks if t.status == status]
        if agent_type is not None:
            tasks = [t for t in tasks if t.agent_type == agent_type]
        # Sort by created_at for stable ordering
        tasks.sort(key=lambda t: t.created_at)
        return [copy.deepcopy(t) for t in tasks[offset : offset + limit]]

    def delete(self, task_id: uuid.UUID) -> bool:
        return self._tasks.pop(task_id, None) is not None

    def count(
        self,
        status: TaskStatus | None = None,
        agent_type: str | None = None,
    ) -> int:
        tasks = list(self._tasks.values())
        if status is not None:
            tasks = [t for t in tasks if t.status == status]
        if agent_type is not None:
            tasks = [t for t in tasks if t.agent_type == agent_type]
        return len(tasks)
