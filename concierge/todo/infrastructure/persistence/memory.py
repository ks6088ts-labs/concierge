from __future__ import annotations

import copy
import uuid

from concierge.todo.domain.entities import Task
from concierge.todo.domain.value_objects import TaskStatus


class InMemoryTaskRepository:
    def __init__(self):
        self._tasks: dict[uuid.UUID, Task] = {}

    def save(self, task: Task) -> Task:
        self._tasks[task.id] = copy.deepcopy(task)
        return copy.deepcopy(self._tasks[task.id])

    def find_by_id(self, task_id: uuid.UUID) -> Task | None:
        task = self._tasks.get(task_id)
        return copy.deepcopy(task) if task is not None else None

    def find_all(self, status: TaskStatus | None = None) -> list[Task]:
        tasks = self._tasks.values()
        if status is not None:
            tasks = (task for task in tasks if task.status == status)
        return [copy.deepcopy(task) for task in tasks]

    def delete(self, task_id: uuid.UUID) -> bool:
        return self._tasks.pop(task_id, None) is not None
