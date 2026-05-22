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
from concierge.agents.infrastructure.langgraph_image_gen_agent import LangGraphImageGenAgent
from concierge.agents.infrastructure.microsoft_agent_framework_echo_agent import (
    MicrosoftAgentFrameworkEchoAgent,
)
from concierge.agents.infrastructure.microsoft_agent_framework_image_gen_agent import (
    MicrosoftAgentFrameworkImageGenAgent,
)
from concierge.observability import trace_config
from concierge.settings.agents import get_agents_settings
from concierge.settings.microsoft_foundry import get_microsoft_foundry_settings


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


def _microsoft_agent_framework_echo_run_config(request: AgentRequest) -> RunnableConfig:
    return trace_config(
        "cloud-agent-microsoft-agent-framework-echo",
        {
            "run_name": "microsoft-agent-framework-echo",
            "metadata": {"task_id": request.context.get("task_id", "")},
        },
    )


def _langgraph_image_gen_run_config(request: AgentRequest) -> RunnableConfig:
    return trace_config(
        "cloud-agent-langgraph-image-gen",
        {
            "run_name": "langgraph-image-gen",
            "metadata": {"task_id": request.context.get("task_id", "")},
        },
    )


def _microsoft_agent_framework_image_gen_run_config(request: AgentRequest) -> RunnableConfig:
    return trace_config(
        "cloud-agent-microsoft-agent-framework-image-gen",
        {
            "run_name": "microsoft-agent-framework-image-gen",
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
    registry.register(
        MicrosoftAgentFrameworkEchoAgent(
            model=settings.microsoft_agent_framework_model,
            system_prompt=settings.microsoft_agent_framework_system_prompt,
            project_endpoint=get_microsoft_foundry_settings().azure_ai_project_endpoint,
            run_config_factory=_microsoft_agent_framework_echo_run_config,
        )
    )
    registry.register(
        LangGraphImageGenAgent(
            model=settings.langgraph_model,
            system_prompt=settings.langgraph_image_gen_system_prompt,
            run_config_factory=_langgraph_image_gen_run_config,
        )
    )
    registry.register(
        MicrosoftAgentFrameworkImageGenAgent(
            model=settings.microsoft_agent_framework_model,
            system_prompt=settings.microsoft_agent_framework_image_gen_system_prompt,
            project_endpoint=get_microsoft_foundry_settings().azure_ai_project_endpoint,
            run_config_factory=_microsoft_agent_framework_image_gen_run_config,
        )
    )
    return registry
