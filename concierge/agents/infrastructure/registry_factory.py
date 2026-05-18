"""Default agent registry factory.

Agents are registered here at application startup.

This module is also the wiring point for cross-cutting concerns (tracing
callbacks, run metadata, ...): individual agent classes stay decoupled from
:mod:`concierge.observability`, and the registry passes them a factory that
builds a per-request :class:`RunnableConfig`.
"""

from __future__ import annotations

from functools import lru_cache

from langchain_core.runnables import RunnableConfig

from concierge.agents.application.contracts import AgentRequest
from concierge.agents.application.registry import AgentRegistry
from concierge.agents.infrastructure.echo_agent import EchoAgent
from concierge.agents.infrastructure.github_copilot_echo_agent import GitHubCopilotEchoAgent
from concierge.agents.infrastructure.langgraph_echo_agent import LangGraphEchoAgent
from concierge.observability import trace_config
from concierge.settings.agents import get_agents_settings


def _langgraph_echo_run_config(request: AgentRequest) -> RunnableConfig:
    """Build a tracing-aware ``RunnableConfig`` for langgraph-echo runs.

    When tracing is disabled at the application level, ``trace_config``
    returns a plain config without callbacks, so this factory is safe to
    call unconditionally.
    """
    return trace_config(
        "cloud-agent-langgraph-echo",
        {
            "run_name": "langgraph-echo",
            "metadata": {"task_id": request.context.get("task_id", "")},
        },
    )


def _github_copilot_echo_run_config(request: AgentRequest) -> RunnableConfig:
    return trace_config(
        "cloud-agent-github-copilot-echo",
        {
            "run_name": "github-copilot-echo",
            "metadata": {"task_id": request.context.get("task_id", "")},
        },
    )


@lru_cache(maxsize=1)
def get_agent_registry() -> AgentRegistry:
    """Return the default AgentRegistry with all built-in agents registered."""
    settings = get_agents_settings()
    registry = AgentRegistry()
    registry.register(EchoAgent())
    registry.register(
        LangGraphEchoAgent(
            model=settings.langgraph_model,
            system_prompt=settings.langgraph_system_prompt,
            run_config_factory=_langgraph_echo_run_config,
        )
    )
    registry.register(
        GitHubCopilotEchoAgent(
            model=settings.github_copilot_model,
            system_prompt=settings.github_copilot_system_prompt,
            run_config_factory=_github_copilot_echo_run_config,
        )
    )
    return registry
