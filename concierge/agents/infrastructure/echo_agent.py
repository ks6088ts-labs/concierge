"""Echo agent - a no-op agent for testing and verification.

Returns the ``payload.message`` value back as the result.  The payload
contract is intentionally aligned with :class:`LangGraphAgent` (echo
preset) so that clients can use the same dispatch payload
(``{"message": "..."}``) for both agents.
"""

from __future__ import annotations

from typing import Any

from concierge.agents.application.contracts import AgentRequest, AgentResponse
from concierge.agents.domain.agent_types import AgentType


class EchoAgent:
    """Agent that echoes ``payload.message`` back as the result."""

    agent_type: str = AgentType.ECHO.value

    async def handle(self, request: AgentRequest) -> AgentResponse:
        message = self._extract_message(request.payload)
        image_url = self._extract_image_url(request.payload)
        if not message and not image_url:
            return AgentResponse(
                status="failed",
                error="payload.message is required (non-empty string)",
            )
        # Echo is text-only, so it cannot interpret the image — but it
        # acknowledges receipt so the shared image-input contract is observable
        # end-to-end even for agents that don't (yet) support vision.
        reply = message
        if image_url:
            reply = f"{message} 🖼️（画像を受信しました）".strip()
        return AgentResponse(
            status="succeeded",
            result={"message": message, "reply": reply},
        )

    @staticmethod
    def _extract_message(payload: dict[str, Any]) -> str:
        value = payload.get("message")
        return value if isinstance(value, str) and value.strip() else ""

    @staticmethod
    def _extract_image_url(payload: dict[str, Any]) -> str:
        value = payload.get("image_url")
        return value if isinstance(value, str) and value.strip() else ""
