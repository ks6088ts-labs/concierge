from __future__ import annotations

from concierge.agents.application.registry import AgentRegistry
from concierge.agents.infrastructure.registry_factory import get_agent_registry
from concierge.cloud_agent.application.queues import TaskQueue
from concierge.cloud_agent.application.repositories import TaskRepository
from concierge.cloud_agent.infrastructure.persistence.factory import get_task_repository as _get_repo
from concierge.cloud_agent.infrastructure.queue.factory import get_task_queue as _get_queue
from concierge.settings import get_cloud_agent_settings


def get_task_repository() -> TaskRepository:
    return _get_repo()


def get_task_queue() -> TaskQueue:
    return _get_queue()


def get_agent_registry_dep() -> AgentRegistry:
    return get_agent_registry()


def get_default_max_retries() -> int:
    return get_cloud_agent_settings().max_retries
