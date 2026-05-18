"""Cloud Agent ↔ shared agents package adapter.

Cloud Agent re-exports the shared contracts so existing internal imports
keep working at one layer of indirection.
"""

from __future__ import annotations

from concierge.agents.application.contracts import Agent, AgentRequest, AgentResponse
from concierge.agents.application.registry import AgentRegistry

__all__ = ["Agent", "AgentRequest", "AgentResponse", "AgentRegistry"]
