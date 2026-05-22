"""Tests for cloud_agent use cases."""

from __future__ import annotations

import uuid
from typing import ClassVar

import pytest

from concierge.agents.domain.agent_types import AgentType
from concierge.cloud_agent.application.agents import AgentRegistry, AgentRequest, AgentResponse
from concierge.cloud_agent.application.use_cases import (
    CancelTaskUseCase,
    DispatchTaskUseCase,
    GetTaskUseCase,
    ListTasksUseCase,
    ProcessNextTaskUseCase,
    UpdateTaskResultUseCase,
)
from concierge.cloud_agent.domain.entities import Task
from concierge.cloud_agent.domain.exceptions import TaskNotFoundError, TaskStateError
from concierge.cloud_agent.domain.value_objects import TaskStatus
from concierge.cloud_agent.infrastructure.persistence.memory import InMemoryTaskRepository
from concierge.cloud_agent.infrastructure.queue.memory import InMemoryTaskQueue


class _FailAgent:
    agent_type: ClassVar[str] = "fail"

    async def handle(self, request: AgentRequest) -> AgentResponse:
        return AgentResponse(status="failed", error="deliberate failure")


class _SucceedAgent:
    agent_type: ClassVar[str] = "succeed"

    async def handle(self, request: AgentRequest) -> AgentResponse:
        return AgentResponse(status="succeeded", result={"done": True})


class _RaiseAgent:
    agent_type: ClassVar[str] = "raise"

    async def handle(self, request: AgentRequest) -> AgentResponse:
        raise RuntimeError("unexpected crash")


@pytest.mark.anyio
async def test_dispatch_creates_and_enqueues_task() -> None:
    repo = InMemoryTaskRepository()
    queue = InMemoryTaskQueue()
    task = await DispatchTaskUseCase(repo, queue).execute(agent_type=AgentType.ECHO, payload={"k": "v"})
    assert task.status == TaskStatus.QUEUED
    assert await queue.size() == 1
    found = repo.find_by_id(task.id)
    assert found is not None


@pytest.mark.anyio
async def test_get_task_not_found_raises() -> None:
    repo = InMemoryTaskRepository()
    with pytest.raises(TaskNotFoundError):
        GetTaskUseCase(repo).execute(uuid.uuid4())


@pytest.mark.anyio
async def test_list_tasks_filters() -> None:
    repo = InMemoryTaskRepository()
    queue = InMemoryTaskQueue()
    await DispatchTaskUseCase(repo, queue).execute(agent_type=AgentType.ECHO, payload={})
    t2 = Task(agent_type="other", payload={})
    t2.mark_running()
    t2.mark_succeeded({})
    repo.save(t2)

    queued = ListTasksUseCase(repo).execute(status=TaskStatus.QUEUED)
    assert len(queued) == 1
    by_agent = ListTasksUseCase(repo).execute(agent_type=AgentType.ECHO)
    assert len(by_agent) == 1


@pytest.mark.anyio
async def test_cancel_queued_task() -> None:
    repo = InMemoryTaskRepository()
    queue = InMemoryTaskQueue()
    task = await DispatchTaskUseCase(repo, queue).execute(agent_type=AgentType.ECHO, payload={})
    cancelled = CancelTaskUseCase(repo).execute(task.id)
    assert cancelled.status == TaskStatus.CANCELLED


@pytest.mark.anyio
async def test_cancel_succeeded_task_raises() -> None:
    repo = InMemoryTaskRepository()
    task = Task(agent_type=AgentType.ECHO, payload={})
    task.mark_running()
    task.mark_succeeded({})
    repo.save(task)
    with pytest.raises(TaskStateError):
        CancelTaskUseCase(repo).execute(task.id)


@pytest.mark.anyio
async def test_update_task_result() -> None:
    repo = InMemoryTaskRepository()
    task = Task(agent_type=AgentType.ECHO, payload={})
    task.mark_running()
    repo.save(task)
    updated = UpdateTaskResultUseCase(repo).execute(task.id, status=TaskStatus.SUCCEEDED, result={"out": 1})
    assert updated.status == TaskStatus.SUCCEEDED
    assert updated.result == {"out": 1}


@pytest.mark.anyio
async def test_process_next_task_succeeds() -> None:
    repo = InMemoryTaskRepository()
    queue = InMemoryTaskQueue()
    registry = AgentRegistry()
    registry.register(_SucceedAgent())

    task = await DispatchTaskUseCase(repo, queue).execute(agent_type="succeed", payload={})
    processed = await ProcessNextTaskUseCase(repo, queue, registry).execute()
    assert processed is True

    found = repo.find_by_id(task.id)
    assert found is not None
    assert found.status == TaskStatus.SUCCEEDED


@pytest.mark.anyio
async def test_process_next_task_empty_queue() -> None:
    repo = InMemoryTaskRepository()
    queue = InMemoryTaskQueue()
    registry = AgentRegistry()
    processed = await ProcessNextTaskUseCase(repo, queue, registry).execute()
    assert processed is False


@pytest.mark.anyio
async def test_process_next_task_failed_retries() -> None:
    repo = InMemoryTaskRepository()
    queue = InMemoryTaskQueue()
    registry = AgentRegistry()
    registry.register(_FailAgent())

    task = await DispatchTaskUseCase(repo, queue).execute(agent_type="fail", payload={}, max_retries=1)
    # First attempt: fail -> re-queue (retry_count=1, max_retries=1, should_retry=True)
    await ProcessNextTaskUseCase(repo, queue, registry).execute()
    found = repo.find_by_id(task.id)
    assert found is not None
    assert found.status == TaskStatus.QUEUED
    assert found.retry_count == 1

    # Second attempt: fail -> retry_count=2 > max_retries=1, -> DEAD_LETTER
    await ProcessNextTaskUseCase(repo, queue, registry).execute()
    found = repo.find_by_id(task.id)
    assert found is not None
    assert found.status == TaskStatus.DEAD_LETTER


@pytest.mark.anyio
async def test_process_next_task_agent_not_found() -> None:
    repo = InMemoryTaskRepository()
    queue = InMemoryTaskQueue()
    registry = AgentRegistry()

    task = await DispatchTaskUseCase(repo, queue).execute(agent_type="unknown", payload={}, max_retries=0)
    await ProcessNextTaskUseCase(repo, queue, registry).execute()
    found = repo.find_by_id(task.id)
    assert found is not None
    assert found.status == TaskStatus.DEAD_LETTER


@pytest.mark.anyio
async def test_process_next_task_exception_retries() -> None:
    repo = InMemoryTaskRepository()
    queue = InMemoryTaskQueue()
    registry = AgentRegistry()
    registry.register(_RaiseAgent())

    task = await DispatchTaskUseCase(repo, queue).execute(agent_type="raise", payload={}, max_retries=0)
    await ProcessNextTaskUseCase(repo, queue, registry).execute()
    found = repo.find_by_id(task.id)
    assert found is not None
    assert found.status == TaskStatus.DEAD_LETTER
