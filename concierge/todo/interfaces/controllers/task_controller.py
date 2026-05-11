from __future__ import annotations

from typing import TypeVar
from uuid import UUID

from concierge.todo.application.dtos.task_dtos import (
    CreateTaskRequest,
    ListTasksRequest,
    TaskResponse,
    UpdateTaskRequest,
)
from concierge.todo.application.use_cases.task_use_cases import (
    CompleteTaskUseCase,
    CreateTaskUseCase,
    DeleteTaskUseCase,
    GetTaskUseCase,
    ListTasksUseCase,
    UpdateTaskUseCase,
)
from concierge.todo.domain.exceptions import DomainError

T = TypeVar("T")


class TaskController:
    def __init__(
        self,
        *,
        create_task: CreateTaskUseCase,
        get_task: GetTaskUseCase,
        list_tasks: ListTasksUseCase,
        update_task: UpdateTaskUseCase,
        complete_task: CompleteTaskUseCase,
        delete_task: DeleteTaskUseCase,
    ):
        self._create_task = create_task
        self._get_task = get_task
        self._list_tasks = list_tasks
        self._update_task = update_task
        self._complete_task = complete_task
        self._delete_task = delete_task

    def create(self, request: CreateTaskRequest) -> TaskResponse:
        result = self._create_task.execute(request)
        return _unwrap(result.value, result.error)

    def get(self, task_id: UUID) -> TaskResponse:
        result = self._get_task.execute(task_id)
        return _unwrap(result.value, result.error)

    def list(self, request: ListTasksRequest) -> list[TaskResponse]:
        result = self._list_tasks.execute(request)
        return _unwrap(result.value, result.error)

    def update(self, task_id: UUID, request: UpdateTaskRequest) -> TaskResponse:
        result = self._update_task.execute(task_id, request)
        return _unwrap(result.value, result.error)

    def complete(self, task_id: UUID) -> TaskResponse:
        result = self._complete_task.execute(task_id)
        return _unwrap(result.value, result.error)

    def delete(self, task_id: UUID) -> None:
        result = self._delete_task.execute(task_id)
        _unwrap(result.value, result.error)


def _unwrap(value: T | None, error: DomainError | None) -> T:
    if error is not None:
        raise error
    return value
