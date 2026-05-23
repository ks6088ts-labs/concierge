"""Unit tests for the built-in EchoAgent.

The payload contract is intentionally aligned with LangGraphAgent (echo preset) so the
same dispatch payload (``{"message": "..."}``) works for either agent.
"""

from __future__ import annotations

import uuid

import pytest

from concierge.agents.application.contracts import AgentRequest
from concierge.agents.domain.agent_types import AgentType
from concierge.agents.infrastructure.echo_agent import EchoAgent

_FAKE_TASK_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _make_task_input(payload: dict) -> AgentRequest:
    return AgentRequest(agent_type=AgentType.ECHO, payload=payload, context={"task_id": str(_FAKE_TASK_ID)})


@pytest.mark.anyio
async def test_echo_agent_succeeds_on_message() -> None:
    agent = EchoAgent()
    output = await agent.handle(_make_task_input({"message": "hello"}))

    assert output.status == "succeeded"
    assert output.result == {"message": "hello", "reply": "hello"}
    assert output.error is None


@pytest.mark.anyio
async def test_echo_agent_fails_when_message_missing() -> None:
    agent = EchoAgent()
    output = await agent.handle(_make_task_input({}))

    assert output.status == "failed"
    assert output.error == "payload.message is required (non-empty string)"


@pytest.mark.anyio
async def test_echo_agent_fails_when_message_empty() -> None:
    agent = EchoAgent()
    output = await agent.handle(_make_task_input({"message": "   "}))

    assert output.status == "failed"
    assert output.error == "payload.message is required (non-empty string)"


@pytest.mark.anyio
async def test_echo_agent_fails_when_message_not_string() -> None:
    agent = EchoAgent()
    output = await agent.handle(_make_task_input({"message": 42}))

    assert output.status == "failed"
    assert output.error == "payload.message is required (non-empty string)"
