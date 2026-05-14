from __future__ import annotations

from functools import lru_cache

from concierge.todo.application.repositories import TaskRepository
from concierge.todo.infrastructure.persistence.memory import InMemoryTaskRepository


@lru_cache(maxsize=1)
def get_task_repository() -> TaskRepository:
    return InMemoryTaskRepository()
