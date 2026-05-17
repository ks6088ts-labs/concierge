"""Echo agent - a no-op agent for testing and verification.

Returns the ``payload.message`` value back as the result.  The payload
contract is intentionally aligned with :class:`LangGraphEchoAgent` so that
clients can use the same dispatch payload (``{"message": "..."}``) for
both agents.
"""

from __future__ import annotations

from typing import Any, ClassVar

from concierge.cloud_agent.application.agents import TaskInput, TaskOutput


class EchoAgent:
    """Agent that echoes ``payload.message`` back as the result."""

    agent_type: ClassVar[str] = "echo"

    async def handle(self, task_input: TaskInput) -> TaskOutput:
        message = self._extract_message(task_input.payload)
        if not message:
            return TaskOutput(
                status="failed",
                error="payload.message is required (non-empty string)",
            )
        return TaskOutput(
            status="succeeded",
            result={"echo": message, "reply": message},
        )

    @staticmethod
    def _extract_message(payload: dict[str, Any]) -> str:
        value = payload.get("message")
        return value if isinstance(value, str) and value.strip() else ""
