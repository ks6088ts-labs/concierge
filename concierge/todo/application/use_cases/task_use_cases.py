from __future__ import annotations

from uuid import UUID

from concierge.todo.application.common.result import Result
from concierge.todo.application.dtos.task_dtos import (
    CreateTaskRequest,
    ListTasksRequest,
    TaskResponse,
    UpdateTaskRequest,
)
from concierge.todo.application.repositories.task_repository import TaskRepository
from concierge.todo.domain.entities.task import Task
from concierge.todo.domain.exceptions import DomainError, TaskNotFoundError, TaskValidationError


class CreateTaskUseCase:
    def __init__(self, repository: TaskRepository):
        self.repository = repository

    def execute(self, request: CreateTaskRequest) -> Result[TaskResponse, DomainError]:
        try:
            task = Task.create(title=request.title, description=request.description)
        except TaskValidationError as error:
            return Result.err(error)
        return Result.ok(TaskResponse.from_entity(self.repository.create(task)))


class GetTaskUseCase:
    def __init__(self, repository: TaskRepository):
        self.repository = repository

    def execute(self, task_id: UUID) -> Result[TaskResponse, DomainError]:
        task = self.repository.get(task_id)
        if task is None:
            return Result.err(TaskNotFoundError(task_id))
        return Result.ok(TaskResponse.from_entity(task))


class ListTasksUseCase:
    def __init__(self, repository: TaskRepository):
        self.repository = repository

    def execute(self, request: ListTasksRequest) -> Result[list[TaskResponse], DomainError]:
        return Result.ok([TaskResponse.from_entity(task) for task in self.repository.list(status=request.status)])


class UpdateTaskUseCase:
    def __init__(self, repository: TaskRepository):
        self.repository = repository

    def execute(self, task_id: UUID, request: UpdateTaskRequest) -> Result[TaskResponse, DomainError]:
        task = self.repository.get(task_id)
        if task is None:
            return Result.err(TaskNotFoundError(task_id))
        try:
            updated_task = task.update(
                title=request.title,
                description=request.description,
                status=request.status,
            )
        except TaskValidationError as error:
            return Result.err(error)
        return Result.ok(TaskResponse.from_entity(self.repository.update(updated_task)))


class CompleteTaskUseCase:
    def __init__(self, repository: TaskRepository):
        self.repository = repository

    def execute(self, task_id: UUID) -> Result[TaskResponse, DomainError]:
        task = self.repository.get(task_id)
        if task is None:
            return Result.err(TaskNotFoundError(task_id))
        return Result.ok(TaskResponse.from_entity(self.repository.update(task.complete())))


class DeleteTaskUseCase:
    def __init__(self, repository: TaskRepository):
        self.repository = repository

    def execute(self, task_id: UUID) -> Result[None, DomainError]:
        if not self.repository.delete(task_id):
            return Result.err(TaskNotFoundError(task_id))
        return Result.ok(None)
