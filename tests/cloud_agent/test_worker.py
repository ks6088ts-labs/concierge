"""Tests for the cloud_agent CLI worker loop."""

from __future__ import annotations

from typing import ClassVar

import pytest

from concierge.cloud_agent.application.agents import AgentRegistry, AgentRequest, AgentResponse
from concierge.cloud_agent.application.use_cases import DispatchTaskUseCase, ProcessNextTaskUseCase
from concierge.cloud_agent.domain.value_objects import TaskStatus
from concierge.cloud_agent.infrastructure.persistence.memory import InMemoryTaskRepository
from concierge.cloud_agent.infrastructure.queue.memory import InMemoryTaskQueue


class _EchoAgent:
    agent_type: ClassVar[str] = "echo"

    async def handle(self, request: AgentRequest) -> AgentResponse:
        return AgentResponse(status="succeeded", result={"echo": request.payload})


@pytest.mark.anyio
async def test_worker_processes_one_task() -> None:
    """Worker loop should process a queued task and mark it SUCCEEDED."""
    repo = InMemoryTaskRepository()
    queue = InMemoryTaskQueue()
    registry = AgentRegistry()
    registry.register(_EchoAgent())

    # Dispatch a task
    task = await DispatchTaskUseCase(repo, queue).execute(agent_type="echo", payload={"msg": "hi"})
    assert task.status == TaskStatus.QUEUED

    # Run worker for one iteration
    use_case = ProcessNextTaskUseCase(repo, queue, registry)
    processed = await use_case.execute()
    assert processed is True

    found = repo.find_by_id(task.id)
    assert found is not None
    assert found.status == TaskStatus.SUCCEEDED
    assert found.result == {"echo": {"msg": "hi"}}


@pytest.mark.anyio
async def test_worker_with_max_iterations(monkeypatch: pytest.MonkeyPatch) -> None:
    """run_worker should stop after max_iterations."""
    from concierge.cloud_agent.infrastructure.cli.worker import run_worker

    repo = InMemoryTaskRepository()
    queue = InMemoryTaskQueue()
    registry = AgentRegistry()
    registry.register(_EchoAgent())

    # Monkeypatch factories to use our in-memory objects
    import concierge.cloud_agent.infrastructure.cli.worker as worker_module

    monkeypatch.setattr(worker_module, "get_task_repository", lambda: repo)
    monkeypatch.setattr(worker_module, "get_task_queue", lambda: queue)
    monkeypatch.setattr(worker_module, "get_agent_registry", lambda: registry)

    # Dispatch a task
    await DispatchTaskUseCase(repo, queue).execute(agent_type="echo", payload={})
    # Run for 2 iterations
    await run_worker(max_iterations=2)

    tasks = repo.find_all(status=TaskStatus.SUCCEEDED)
    assert len(tasks) == 1
