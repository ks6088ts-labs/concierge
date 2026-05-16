from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from concierge.cloud_agent.application.agents import AgentRegistry
from concierge.cloud_agent.application.queues import TaskQueue
from concierge.cloud_agent.application.repositories import TaskRepository
from concierge.cloud_agent.application.use_cases import (
    CancelTaskUseCase,
    DispatchTaskUseCase,
    GetTaskUseCase,
    ListTasksUseCase,
    UpdateTaskResultUseCase,
)
from concierge.cloud_agent.domain.value_objects import TaskStatus
from concierge.cloud_agent.infrastructure.web.dependencies import (
    get_agent_registry_dep,
    get_default_max_retries,
    get_task_queue,
    get_task_repository,
)
from concierge.cloud_agent.infrastructure.web.schemas import (
    AgentListResponse,
    DispatchTaskRequest,
    TaskResponse,
    UpdateTaskRequest,
)

router = APIRouter(prefix="/cloud-agent", tags=["cloud-agent"])


@router.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def dispatch_task(
    payload: DispatchTaskRequest,
    repository: Annotated[TaskRepository, Depends(get_task_repository)],
    queue: Annotated[TaskQueue, Depends(get_task_queue)],
    registry: Annotated[AgentRegistry, Depends(get_agent_registry_dep)],
    max_retries: Annotated[int, Depends(get_default_max_retries)],
) -> TaskResponse:
    # Validate agent_type is registered
    registry.resolve(payload.agent_type)
    use_case = DispatchTaskUseCase(repository, queue, max_retries=max_retries)
    task = await use_case.execute(
        agent_type=payload.agent_type,
        payload=payload.payload,
        max_retries=payload.max_retries,
    )
    return TaskResponse.model_validate(task)


@router.get("/tasks", response_model=list[TaskResponse])
def list_tasks(
    repository: Annotated[TaskRepository, Depends(get_task_repository)],
    status: TaskStatus | None = None,
    agent_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[TaskResponse]:
    tasks = ListTasksUseCase(repository).execute(
        status=status,
        agent_type=agent_type,
        limit=limit,
        offset=offset,
    )
    return [TaskResponse.model_validate(t) for t in tasks]


@router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: uuid.UUID,
    repository: Annotated[TaskRepository, Depends(get_task_repository)],
) -> TaskResponse:
    task = GetTaskUseCase(repository).execute(task_id)
    return TaskResponse.model_validate(task)


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
def update_task_result(
    task_id: uuid.UUID,
    payload: UpdateTaskRequest,
    repository: Annotated[TaskRepository, Depends(get_task_repository)],
) -> TaskResponse:
    task = UpdateTaskResultUseCase(repository).execute(
        task_id=task_id,
        status=payload.status,
        result=payload.result,
        error=payload.error,
    )
    return TaskResponse.model_validate(task)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_task(
    task_id: uuid.UUID,
    repository: Annotated[TaskRepository, Depends(get_task_repository)],
) -> Response:
    CancelTaskUseCase(repository).execute(task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/agents", response_model=AgentListResponse)
def list_agents(
    registry: Annotated[AgentRegistry, Depends(get_agent_registry_dep)],
) -> AgentListResponse:
    return AgentListResponse(agent_types=registry.list_agent_types())
