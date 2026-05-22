"""Default agent registry factory.

Agents are registered here at application startup.

This module is also the wiring point for cross-cutting concerns (tracing
callbacks, run metadata, ...): individual agent classes stay decoupled from
:mod:`concierge.observability`, and the registry passes them a factory that
builds a per-request :class:`RunnableConfig`.

The framework-backed agents (LangGraph / Microsoft Agent Framework) are
instantiated as *presets* of a single underlying class — different
``agent_type`` ids share the same class but compose different tool
builders. Adding a new tool variant means adding another preset here, not
another agent class.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from langchain_core.runnables import RunnableConfig

from concierge.agents.application.contracts import AgentRequest
from concierge.agents.application.registry import AgentRegistry
from concierge.agents.domain.agent_types import AgentType
from concierge.agents.infrastructure.echo_agent import EchoAgent
from concierge.agents.infrastructure.github_copilot_echo_agent import GitHubCopilotEchoAgent
from concierge.agents.infrastructure.langgraph_agent import LangGraphAgent
from concierge.agents.infrastructure.microsoft_agent_framework_agent import MicrosoftAgentFrameworkAgent
from concierge.agents.infrastructure.tools import (
    build_echo_langchain_tool,
    build_echo_maf_tool,
    image_gen_langchain_tool_factory,
    image_gen_maf_tool_factory,
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
            "run_name": AgentType.LANGGRAPH_ECHO.value,
            "metadata": {"task_id": request.context.get("task_id", "")},
        },
    )


def _github_copilot_echo_run_config(request: AgentRequest) -> RunnableConfig:
    return trace_config(
        "cloud-agent-github-copilot-echo",
        {
            "run_name": AgentType.GITHUB_COPILOT_ECHO.value,
            "metadata": {"task_id": request.context.get("task_id", "")},
        },
    )


def _microsoft_agent_framework_echo_run_config(request: AgentRequest) -> RunnableConfig:
    return trace_config(
        "cloud-agent-microsoft-agent-framework-echo",
        {
            "run_name": AgentType.MICROSOFT_AGENT_FRAMEWORK_ECHO.value,
            "metadata": {"task_id": request.context.get("task_id", "")},
        },
    )


def _langgraph_image_gen_run_config(request: AgentRequest) -> RunnableConfig:
    return trace_config(
        "cloud-agent-langgraph-image-gen",
        {
            "run_name": AgentType.LANGGRAPH_IMAGE_GEN.value,
            "metadata": {"task_id": request.context.get("task_id", "")},
        },
    )


def _microsoft_agent_framework_image_gen_run_config(request: AgentRequest) -> RunnableConfig:
    return trace_config(
        "cloud-agent-microsoft-agent-framework-image-gen",
        {
            "run_name": AgentType.MICROSOFT_AGENT_FRAMEWORK_IMAGE_GEN.value,
            "metadata": {"task_id": request.context.get("task_id", "")},
        },
    )


def _image_save_dir() -> str:
    return str((Path.cwd() / "generated_images").resolve())


@lru_cache(maxsize=1)
def get_agent_registry() -> AgentRegistry:
    """Return the default AgentRegistry with all built-in agents registered."""
    settings = get_agents_settings()
    foundry_endpoint = get_microsoft_foundry_settings().azure_ai_project_endpoint
    save_dir = _image_save_dir()

    registry = AgentRegistry()
    registry.register(EchoAgent())
    registry.register(
        LangGraphAgent(
            agent_type=AgentType.LANGGRAPH_ECHO.value,
            model=settings.langgraph_model,
            system_prompt=settings.langgraph_system_prompt,
            tool_builders=[build_echo_langchain_tool],
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
        MicrosoftAgentFrameworkAgent(
            agent_type=AgentType.MICROSOFT_AGENT_FRAMEWORK_ECHO.value,
            model=settings.microsoft_agent_framework_model,
            system_prompt=settings.microsoft_agent_framework_system_prompt,
            tool_builders=[build_echo_maf_tool],
            project_endpoint=foundry_endpoint,
            run_config_factory=_microsoft_agent_framework_echo_run_config,
        )
    )
    registry.register(
        LangGraphAgent(
            agent_type=AgentType.LANGGRAPH_IMAGE_GEN.value,
            model=settings.langgraph_model,
            system_prompt=settings.langgraph_image_gen_system_prompt,
            tool_builders=[image_gen_langchain_tool_factory(save_dir)],
            run_config_factory=_langgraph_image_gen_run_config,
        )
    )
    registry.register(
        MicrosoftAgentFrameworkAgent(
            agent_type=AgentType.MICROSOFT_AGENT_FRAMEWORK_IMAGE_GEN.value,
            model=settings.microsoft_agent_framework_model,
            system_prompt=settings.microsoft_agent_framework_image_gen_system_prompt,
            tool_builders=[image_gen_maf_tool_factory(save_dir)],
            project_endpoint=foundry_endpoint,
            run_config_factory=_microsoft_agent_framework_image_gen_run_config,
        )
    )
    return registry
