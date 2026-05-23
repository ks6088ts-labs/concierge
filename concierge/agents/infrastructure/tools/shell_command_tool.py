"""Shell-command tool builders for LangChain, MAF, and Copilot SDK."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from pydantic import BaseModel, Field

from concierge.agents.infrastructure.tools.exceptions import ShellToolError
from concierge.agents.infrastructure.tools.shell_command import SHELL_TOOL_NAMES, ShellCommandConfig, ShellCommandCore


class _ShellExecParams(BaseModel):
    command: str | list[str] = Field(description="Shell command string or argv list to execute")


def parse_enabled_shell_tools(value: str | Sequence[str]) -> list[str]:
    if isinstance(value, str):
        enabled = [name.strip() for name in value.split(",") if name.strip()]
    else:
        enabled = [str(name).strip() for name in value if str(name).strip()]

    unknown = sorted({name for name in enabled if name not in SHELL_TOOL_NAMES})
    if unknown:
        raise ValueError(f"Unknown shell tool(s): {', '.join(unknown)}")
    return enabled


def _tool_error_to_response(exc: Exception) -> str:
    return f"Error: {exc}"


def _build_langchain_builder(tool_name: str, core: ShellCommandCore) -> Callable[[dict[str, Any]], Any]:
    def _build(_side_outputs: dict[str, Any]) -> Any:
        from langchain_core.tools import tool

        if tool_name == "shell_exec":

            @tool
            def shell_exec(command: str | list[str]) -> str:
                """Execute an allowlisted shell command in the configured sandbox root."""
                try:
                    return core.shell_exec(command)
                except (ShellToolError, ValueError) as exc:
                    return _tool_error_to_response(exc)

            return shell_exec

        raise ValueError(f"Unsupported shell tool: {tool_name}")

    return _build


def build_shell_langchain_tool_builders(
    config: ShellCommandConfig,
    enabled: str | Sequence[str],
) -> list[Callable[[dict[str, Any]], Any]]:
    core = ShellCommandCore(config=config)
    selected = parse_enabled_shell_tools(enabled)
    return [_build_langchain_builder(name, core) for name in selected]


def _build_maf_builder(tool_name: str, core: ShellCommandCore) -> Callable[[dict[str, Any]], Any]:
    def _build(_side_outputs: dict[str, Any]) -> Any:
        from agent_framework import tool

        if tool_name == "shell_exec":

            @tool
            def shell_exec(command: str | list[str]) -> str:
                """Execute an allowlisted shell command in the configured sandbox root."""
                try:
                    return core.shell_exec(command)
                except (ShellToolError, ValueError) as exc:
                    return _tool_error_to_response(exc)

            return shell_exec

        raise ValueError(f"Unsupported shell tool: {tool_name}")

    return _build


def build_shell_maf_tool_builders(
    config: ShellCommandConfig,
    enabled: str | Sequence[str],
) -> list[Callable[[dict[str, Any]], Any]]:
    core = ShellCommandCore(config=config)
    selected = parse_enabled_shell_tools(enabled)
    return [_build_maf_builder(name, core) for name in selected]


def _build_copilot_builder(tool_name: str, core: ShellCommandCore) -> Callable[[dict[str, Any]], Any]:
    def _build(_side_outputs: dict[str, Any]) -> Any:
        from copilot import define_tool

        if tool_name == "shell_exec":

            @define_tool(
                name="shell_exec",
                description="Execute an allowlisted shell command in sandbox root.",
                skip_permission=True,
            )
            def shell_exec(params: _ShellExecParams) -> str:
                try:
                    return core.shell_exec(params.command)
                except (ShellToolError, ValueError) as exc:
                    return _tool_error_to_response(exc)

            return shell_exec

        raise ValueError(f"Unsupported shell tool: {tool_name}")

    return _build


def build_shell_copilot_sdk_tool_builders(
    config: ShellCommandConfig,
    enabled: str | Sequence[str],
) -> list[Callable[[dict[str, Any]], Any]]:
    core = ShellCommandCore(config=config)
    selected = parse_enabled_shell_tools(enabled)
    return [_build_copilot_builder(name, core) for name in selected]
