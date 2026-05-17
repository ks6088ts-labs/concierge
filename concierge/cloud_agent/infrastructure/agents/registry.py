"""Default agent registry.

Agents are registered here at application startup.

This module is also the wiring point for cross-cutting concerns (tracing
callbacks, run metadata, ...): individual agent classes stay decoupled from
:mod:`concierge.observability`, and the registry passes them a factory that
builds a per-task :class:`RunnableConfig`.
"""

from __future__ import annotations

from functools import lru_cache

from langchain_core.runnables import RunnableConfig

from concierge.cloud_agent.application.agents import AgentRegistry, TaskInput
from concierge.cloud_agent.infrastructure.agents.echo_agent import EchoAgent
from concierge.cloud_agent.infrastructure.agents.langgraph_echo_agent import LangGraphEchoAgent
from concierge.observability import trace_config


def _langgraph_echo_run_config(task_input: TaskInput) -> RunnableConfig:
    """Build a tracing-aware ``RunnableConfig`` for langgraph-echo runs.

    When tracing is disabled at the application level, ``trace_config``
    returns a plain config without callbacks, so this factory is safe to
    call unconditionally.
    """
    return trace_config(
        "cloud-agent-langgraph-echo",
        {
            "run_name": "langgraph-echo",
            "metadata": {"task_id": str(task_input.task_id)},
        },
    )


@lru_cache(maxsize=1)
def get_agent_registry() -> AgentRegistry:
    """Return the default AgentRegistry with all built-in agents registered."""
    registry = AgentRegistry()
    registry.register(EchoAgent())
    registry.register(LangGraphEchoAgent(run_config_factory=_langgraph_echo_run_config))
    return registry
