from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from concierge.todo.application.repositories import TaskRepository
from concierge.todo.application.use_cases import (
    CompleteTaskUseCase,
    CreateTaskUseCase,
    DeleteTaskUseCase,
    GetTaskUseCase,
    ListTasksUseCase,
    UpdateTaskUseCase,
)
from concierge.todo.domain.value_objects import TaskStatus
from concierge.todo.infrastructure.web.dependencies import get_task_repository
from concierge.todo.infrastructure.web.schemas import CreateTaskRequest, TaskResponse, UpdateTaskRequest

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: CreateTaskRequest,
    repository: Annotated[TaskRepository, Depends(get_task_repository)],
) -> TaskResponse:
    task = CreateTaskUseCase(repository).execute(title=payload.title, description=payload.description)
    return TaskResponse.model_validate(task)


@router.get("", response_model=list[TaskResponse])
def list_tasks(
    repository: Annotated[TaskRepository, Depends(get_task_repository)],
    status: TaskStatus | None = None,
) -> list[TaskResponse]:
    tasks = ListTasksUseCase(repository).execute(status=status)
    return [TaskResponse.model_validate(task) for task in tasks]


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: uuid.UUID,
    repository: Annotated[TaskRepository, Depends(get_task_repository)],
) -> TaskResponse:
    task = GetTaskUseCase(repository).execute(task_id)
    return TaskResponse.model_validate(task)


@router.patch("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: uuid.UUID,
    payload: UpdateTaskRequest,
    repository: Annotated[TaskRepository, Depends(get_task_repository)],
) -> TaskResponse:
    task = UpdateTaskUseCase(repository).execute(
        task_id=task_id,
        title=payload.title,
        description=payload.description,
        status=payload.status,
    )
    return TaskResponse.model_validate(task)


@router.post("/{task_id}/complete", response_model=TaskResponse)
def complete_task(
    task_id: uuid.UUID,
    repository: Annotated[TaskRepository, Depends(get_task_repository)],
) -> TaskResponse:
    task = CompleteTaskUseCase(repository).execute(task_id)
    return TaskResponse.model_validate(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: uuid.UUID,
    repository: Annotated[TaskRepository, Depends(get_task_repository)],
) -> Response:
    DeleteTaskUseCase(repository).execute(task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
