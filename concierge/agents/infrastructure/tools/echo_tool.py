"""Echo tool builders for LangChain and Microsoft Agent Framework.

The agent classes accept tool *builders* (rather than already-built tools)
so they can pass a fresh ``side_outputs`` dict on every ``handle()`` call.
The echo tool produces no side outputs, so its builder ignores the dict.
"""

from __future__ import annotations

from typing import Any


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
