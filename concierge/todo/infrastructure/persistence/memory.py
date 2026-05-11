from __future__ import annotations

from threading import RLock
from uuid import UUID

from concierge.todo.domain.entities.task import Task
from concierge.todo.domain.value_objects import TaskStatus


class InMemoryTaskRepository:
    def __init__(self):
        self._tasks: dict[UUID, Task] = {}
        self._lock = RLock()

    def create(self, task: Task) -> Task:
        with self._lock:
            self._tasks[task.id] = task
            return task

    def get(self, task_id: UUID) -> Task | None:
        with self._lock:
            return self._tasks.get(task_id)

    def list(self, status: TaskStatus | None = None) -> list[Task]:
        with self._lock:
            tasks = list(self._tasks.values())
        if status is not None:
            tasks = [task for task in tasks if task.status == status]
        return sorted(tasks, key=lambda task: task.created_at)

    def update(self, task: Task) -> Task:
        with self._lock:
            self._tasks[task.id] = task
            return task

    def delete(self, task_id: UUID) -> bool:
        with self._lock:
            return self._tasks.pop(task_id, None) is not None

    def clear(self) -> None:
        with self._lock:
            self._tasks.clear()
