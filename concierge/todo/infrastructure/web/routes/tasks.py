from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from concierge.todo.application.dtos.task_dtos import CreateTaskRequest, ListTasksRequest, UpdateTaskRequest
from concierge.todo.domain.entities.task import UNSET
from concierge.todo.domain.value_objects import TaskStatus
from concierge.todo.infrastructure.web.dependencies import get_api_presenter, get_task_controller
from concierge.todo.infrastructure.web.schemas.task_schemas import (
    TaskCreateSchema,
    TaskListResponseSchema,
    TaskResponseSchema,
    TaskUpdateSchema,
)
from concierge.todo.interfaces.controllers.task_controller import TaskController
from concierge.todo.interfaces.presenters.api import ApiTaskPresenter

router = APIRouter(tags=["tasks"])


@router.post("/tasks", response_model=TaskResponseSchema, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreateSchema,
    controller: TaskController = Depends(get_task_controller),
    presenter: ApiTaskPresenter = Depends(get_api_presenter),
):
    task = controller.create(CreateTaskRequest(title=payload.title, description=payload.description))
    presentation = presenter.present_task(task, status_code=status.HTTP_201_CREATED)
    return presentation.body


@router.get("/tasks", response_model=TaskListResponseSchema)
def list_tasks(
    status: TaskStatus | None = None,
    controller: TaskController = Depends(get_task_controller),
    presenter: ApiTaskPresenter = Depends(get_api_presenter),
):
    tasks = controller.list(ListTasksRequest(status=status))
    return presenter.present_tasks(tasks).body


@router.get("/tasks/{task_id}", response_model=TaskResponseSchema)
def get_task(
    task_id: UUID,
    controller: TaskController = Depends(get_task_controller),
    presenter: ApiTaskPresenter = Depends(get_api_presenter),
):
    task = controller.get(task_id)
    return presenter.present_task(task).body


@router.patch("/tasks/{task_id}", response_model=TaskResponseSchema)
def update_task(
    task_id: UUID,
    payload: TaskUpdateSchema,
    controller: TaskController = Depends(get_task_controller),
    presenter: ApiTaskPresenter = Depends(get_api_presenter),
):
    description = UNSET
    if "description" in payload.model_fields_set:
        description = payload.description
    title = UNSET
    if "title" in payload.model_fields_set and payload.title is not None:
        title = payload.title
    status_value = UNSET
    if "status" in payload.model_fields_set and payload.status is not None:
        status_value = payload.status
    task = controller.update(
        task_id,
        UpdateTaskRequest(title=title, description=description, status=status_value),
    )
    return presenter.present_task(task).body


@router.post("/tasks/{task_id}/complete", response_model=TaskResponseSchema)
def complete_task(
    task_id: UUID,
    controller: TaskController = Depends(get_task_controller),
    presenter: ApiTaskPresenter = Depends(get_api_presenter),
):
    task = controller.complete(task_id)
    return presenter.present_task(task).body


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: UUID,
    controller: TaskController = Depends(get_task_controller),
):
    controller.delete(task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
