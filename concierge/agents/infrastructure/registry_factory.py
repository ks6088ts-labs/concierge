"""Default agent registry factory.

Agents are registered here at application startup.

This module is also the wiring point for cross-cutting concerns (tracing
callbacks, run metadata, ...): individual agent classes stay decoupled from
:mod:`concierge.observability`, and the registry passes them a factory that
builds a per-request :class:`RunnableConfig`.

The framework-backed agents (``langgraph`` / ``microsoft-agent-framework``)
are *generic* — they are constructed once with the full set of tool
builders and rely on the LLM to pick the right tool for each request.
Adding a new tool means adding another builder to the lists below; no
new ``agent_type`` is required.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from langchain_core.runnables import RunnableConfig

from concierge.agents.application.contracts import AgentRequest
from concierge.agents.application.registry import AgentRegistry
from concierge.agents.domain.agent_types import AgentType
from concierge.agents.infrastructure.echo_agent import EchoAgent
from concierge.agents.infrastructure.github_copilot_sdk_agent import GitHubCopilotSdkAgent
from concierge.agents.infrastructure.langgraph_agent import LangGraphAgent
from concierge.agents.infrastructure.microsoft_agent_framework_agent import MicrosoftAgentFrameworkAgent
from concierge.agents.infrastructure.tools import (
    ShellCommandConfig,
    build_echo_copilot_sdk_tool,
    build_echo_langchain_tool,
    build_echo_maf_tool,
    build_file_copilot_sdk_tool_builders,
    build_file_langchain_tool_builders,
    build_file_maf_tool_builders,
    build_shell_copilot_sdk_tool_builders,
    build_shell_langchain_tool_builders,
    build_shell_maf_tool_builders,
    image_gen_copilot_sdk_tool_factory,
    image_gen_langchain_tool_factory,
    image_gen_maf_tool_factory,
    resolve_file_root_dir,
    resolve_shell_root_dir,
)
from concierge.observability import trace_config
from concierge.settings.agents import get_agents_settings
from concierge.settings.microsoft_foundry import get_microsoft_foundry_settings


def _langgraph_run_config(request: AgentRequest) -> RunnableConfig:
    """Build a tracing-aware ``RunnableConfig`` for langgraph runs."""
    return trace_config(
        "concierge-agents-langgraph",
        {
            "run_name": AgentType.LANGGRAPH.value,
            "metadata": {"task_id": request.context.get("task_id", "")},
        },
    )


def _image_save_dir() -> str:
    return str((Path.cwd() / "generated_images").resolve())


def _parse_allowed_commands(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


@lru_cache(maxsize=1)
def get_agent_registry() -> AgentRegistry:
    """Return the default AgentRegistry with all built-in agents registered."""
    settings = get_agents_settings()
    foundry_endpoint = get_microsoft_foundry_settings().azure_ai_project_endpoint
    save_dir = _image_save_dir()
    file_root_dir = str(resolve_file_root_dir(settings.file_root_dir))
    file_builders_lc = build_file_langchain_tool_builders(file_root_dir, settings.file_tools_enabled)
    file_builders_maf = build_file_maf_tool_builders(file_root_dir, settings.file_tools_enabled)
    file_builders_copilot = build_file_copilot_sdk_tool_builders(file_root_dir, settings.file_tools_enabled)
    shell_builders_lc: list = []
    shell_builders_maf: list = []
    shell_builders_copilot: list = []
    if settings.shell_tools_enabled.strip():
        allowed_commands = _parse_allowed_commands(settings.shell_allowed_commands)
        if not allowed_commands:
            raise ValueError("AGENTS_SHELL_ALLOWED_COMMANDS must be set when AGENTS_SHELL_TOOLS_ENABLED is not empty.")
        shell_config = ShellCommandConfig(
            allowed_commands=allowed_commands,
            root_dir=resolve_shell_root_dir(settings.shell_root_dir, fallback=file_root_dir),
            timeout_seconds=settings.shell_timeout_seconds,
            max_output_bytes=settings.shell_max_output_bytes,
        )
        shell_builders_lc = build_shell_langchain_tool_builders(shell_config, settings.shell_tools_enabled)
        shell_builders_maf = build_shell_maf_tool_builders(shell_config, settings.shell_tools_enabled)
        shell_builders_copilot = build_shell_copilot_sdk_tool_builders(shell_config, settings.shell_tools_enabled)

    registry = AgentRegistry()
    registry.register(EchoAgent())
    registry.register(
        LangGraphAgent(
            agent_type=AgentType.LANGGRAPH.value,
            model=settings.langgraph_model,
            system_prompt=settings.langgraph_system_prompt,
            tool_builders=[
                build_echo_langchain_tool,
                image_gen_langchain_tool_factory(save_dir),
                *file_builders_lc,
                *shell_builders_lc,
            ],
            run_config_factory=_langgraph_run_config,
        )
    )
    registry.register(
        GitHubCopilotSdkAgent(
            model=settings.github_copilot_sdk_model,
            system_prompt=settings.github_copilot_sdk_system_prompt,
            tool_builders=[
                build_echo_copilot_sdk_tool,
                image_gen_copilot_sdk_tool_factory(save_dir),
                *file_builders_copilot,
                *shell_builders_copilot,
            ],
        )
    )
    registry.register(
        MicrosoftAgentFrameworkAgent(
            agent_type=AgentType.MICROSOFT_AGENT_FRAMEWORK.value,
            model=settings.microsoft_agent_framework_model,
            system_prompt=settings.microsoft_agent_framework_system_prompt,
            tool_builders=[
                build_echo_maf_tool,
                image_gen_maf_tool_factory(save_dir),
                *file_builders_maf,
                *shell_builders_maf,
            ],
            project_endpoint=foundry_endpoint,
        )
    )
    return registry
