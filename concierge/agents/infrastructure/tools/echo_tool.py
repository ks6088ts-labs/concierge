"""Echo tool builders for LangChain, Microsoft Agent Framework, and GitHub Copilot SDK.

The agent classes accept tool *builders* (rather than already-built tools)
so they can pass a fresh ``side_outputs`` dict on every ``handle()`` call.
The echo tool produces no side outputs, so its builder ignores the dict.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class _EchoParams(BaseModel):
    """Parameter schema for the Copilot SDK echo tool.

    Declared at module level because ``copilot.define_tool`` resolves the
    handler's parameter type via :func:`typing.get_type_hints`, which cannot
    see locally-defined classes under ``from __future__ import annotations``.
    """

    text: str = Field(description="Text to echo back")


def build_echo_langchain_tool(_side_outputs: dict[str, Any]) -> Any:
    from langchain_core.tools import tool

    @tool
    def echo(text: str) -> str:
        """Echo back the given text exactly."""
        return text

    return echo


def build_echo_maf_tool(_side_outputs: dict[str, Any]) -> Any:
    from agent_framework import tool

    @tool
    def echo(text: str) -> str:
        """Echo back the given text exactly."""
        return text

    return echo


def build_echo_copilot_sdk_tool(_side_outputs: dict[str, Any]) -> Any:
    from copilot import define_tool

    @define_tool(
        name="echo",
        description="Echo back the given text exactly.",
        skip_permission=True,
    )
    def echo(params: _EchoParams) -> str:
        return params.text

    return echo
