from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from concierge.todo.application.repositories import TaskRepository
from concierge.todo.domain.entities import Task
from concierge.todo.domain.exceptions import TaskNotFoundError
from concierge.todo.domain.value_objects import TaskStatus

logger = logging.getLogger(__name__)


class CreateTaskUseCase:
    def __init__(self, repository: TaskRepository):
        self.repository = repository

    def execute(self, title: str, description: str | None = None) -> Task:
        task = Task(title=title, description=description)
        created = self.repository.save(task)
        logger.info("Created task id=%s", created.id)
        return created


class GetTaskUseCase:
    def __init__(self, repository: TaskRepository):
        self.repository = repository

    def execute(self, task_id: uuid.UUID) -> Task:
        task = self.repository.find_by_id(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        return task


class ListTasksUseCase:
    def __init__(self, repository: TaskRepository):
        self.repository = repository

    def execute(self, status: TaskStatus | None = None) -> list[Task]:
        return self.repository.find_all(status=status)


class UpdateTaskUseCase:
    def __init__(self, repository: TaskRepository):
        self.repository = repository

    def execute(
        self,
        task_id: uuid.UUID,
        title: str | None = None,
        description: str | None = None,
        status: TaskStatus | None = None,
    ) -> Task:
        task = self.repository.find_by_id(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        if title is not None:
            task._validate_title(title)
            task.title = title
        if description is not None:
            task._validate_description(description)
            task.description = description
        if status is not None:
            task.status = status
        task.updated_at = datetime.now(timezone.utc)
        updated = self.repository.save(task)
        logger.info("Updated task id=%s", updated.id)
        return updated


class CompleteTaskUseCase:
    def __init__(self, repository: TaskRepository):
        self.repository = repository

    def execute(self, task_id: uuid.UUID) -> Task:
        task = self.repository.find_by_id(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        task.status = TaskStatus.DONE
        task.updated_at = datetime.now(timezone.utc)
        completed = self.repository.save(task)
        logger.info("Completed task id=%s", completed.id)
        return completed


class DeleteTaskUseCase:
    def __init__(self, repository: TaskRepository):
        self.repository = repository

    def execute(self, task_id: uuid.UUID) -> None:
        if not self.repository.delete(task_id):
            raise TaskNotFoundError(task_id)
        logger.info("Deleted task id=%s", task_id)
