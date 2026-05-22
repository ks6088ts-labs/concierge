"""Echo agent - a no-op agent for testing and verification.

Returns the ``payload.message`` value back as the result.  The payload
contract is intentionally aligned with :class:`LangGraphEchoAgent` so that
clients can use the same dispatch payload (``{"message": "..."}``) for
both agents.
"""

from __future__ import annotations

from typing import Any, ClassVar

from concierge.agents.application.contracts import AgentRequest, AgentResponse
from concierge.agents.domain.agent_types import AgentType


class EchoAgent:
    """Agent that echoes ``payload.message`` back as the result."""

    agent_type: ClassVar[str] = AgentType.ECHO.value

    async def handle(self, request: AgentRequest) -> AgentResponse:
        message = self._extract_message(request.payload)
        if not message:
            return AgentResponse(
                status="failed",
                error="payload.message is required (non-empty string)",
            )
        return AgentResponse(
            status="succeeded",
            result={"echo": message, "reply": message},
        )

    @staticmethod
    def _extract_message(payload: dict[str, Any]) -> str:
        value = payload.get("message")
        return value if isinstance(value, str) and value.strip() else ""
