from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from concierge.agents.infrastructure.github_copilot_echo_agent import GitHubCopilotEchoAgent
from concierge.agents.infrastructure.registry_factory import get_agent_registry
from concierge.cloud_agent.application.use_cases import DispatchTaskUseCase, ProcessNextTaskUseCase
from concierge.cloud_agent.domain.value_objects import TaskStatus
from concierge.cloud_agent.infrastructure.persistence.memory import InMemoryTaskRepository
from concierge.cloud_agent.infrastructure.queue.memory import InMemoryTaskQueue


@pytest.mark.anyio
async def test_cloud_agent_processes_github_copilot_echo_task() -> None:
    """End-to-end dispatch path: cloud_agent worker drives the github-copilot-echo agent.

    The Copilot SDK session is mocked at ``_run_session`` to keep the test
    hermetic — the cloud_agent layer should be agnostic to how the agent
    obtains its reply.
    """
    get_agent_registry.cache_clear()
    registry = get_agent_registry()
    repository = InMemoryTaskRepository()
    queue = InMemoryTaskQueue()

    task = await DispatchTaskUseCase(repository, queue).execute(
        agent_type="github-copilot-echo",
        payload={"message": "Hello Copilot"},
    )

    with patch.object(
        GitHubCopilotEchoAgent,
        "_run_session",
        new=AsyncMock(return_value="Hello Copilot"),
    ):
        processed = await ProcessNextTaskUseCase(repository, queue, registry).execute()

    assert processed is True

    found = repository.find_by_id(task.id)
    assert found is not None
    assert found.status == TaskStatus.SUCCEEDED
    assert found.result == {
        "echo": "Hello Copilot",
        "reply": "Hello Copilot",
        "model": "gpt-5-mini",
    }
