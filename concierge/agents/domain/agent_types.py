"""Canonical identifiers for registered agents.

``agent_type`` is a domain concept that flows through ``AgentRequest``,
the registry, the CLI, the chat / cloud_agent services, and external
clients. Centralising the identifiers here keeps producers and consumers
in sync and lets type checkers catch typos.

Members inherit from :class:`str` (via :class:`enum.StrEnum`) so existing
``agent_type: str`` annotations, JSON serialisation, and equality with
plain string literals all continue to work unchanged.
"""

from __future__ import annotations

from enum import StrEnum


class AgentType(StrEnum):
    """Registered ``agent_type`` identifiers for built-in agents."""

    ECHO = "echo"
    LANGGRAPH_ECHO = "langgraph-echo"
    GITHUB_COPILOT_ECHO = "github-copilot-echo"
    MICROSOFT_AGENT_FRAMEWORK_ECHO = "microsoft-agent-framework-echo"
    LANGGRAPH_IMAGE_GEN = "langgraph-image-gen"
    MICROSOFT_AGENT_FRAMEWORK_IMAGE_GEN = "microsoft-agent-framework-image-gen"
