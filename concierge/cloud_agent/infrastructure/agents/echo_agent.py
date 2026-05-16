"""Echo agent - a no-op agent for testing and verification.

Echoes the input payload back in the result.
"""

from __future__ import annotations

from typing import ClassVar

from concierge.cloud_agent.application.agents import TaskInput, TaskOutput


class EchoAgent:
    """Agent that echoes the input payload back as the result."""

    agent_type: ClassVar[str] = "echo"

    async def handle(self, task_input: TaskInput) -> TaskOutput:
        return TaskOutput(
            status="succeeded",
            result={"echo": task_input.payload},
        )
