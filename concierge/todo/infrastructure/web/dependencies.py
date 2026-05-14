from __future__ import annotations

from concierge.todo.application.repositories import TaskRepository
from concierge.todo.infrastructure.persistence.factory import get_task_repository as _factory_get_task_repository


def get_task_repository() -> TaskRepository:
    return _factory_get_task_repository()
