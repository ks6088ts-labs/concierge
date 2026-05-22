from __future__ import annotations

import json
import uuid
from collections.abc import Iterator

import pytest
from httpx import ASGITransport, AsyncClient

from concierge.agents.domain.agent_types import AgentType
from concierge.chat.domain.entities import Conversation, Message
from concierge.chat.infrastructure.persistence.memory import InMemoryConversationRepository, InMemoryMessageRepository
from concierge.chat.infrastructure.web.app import create_app
from concierge.chat.infrastructure.web.dependencies import (
    get_chatbot_responder,
    get_conversation_repository,
    get_message_repository,
)


class FakeStreamingResponder:
    def __init__(self, chunks: list[str]) -> None:
        self._chunks = chunks

    def stream_reply(self, conversation: Conversation, history: list[Message]) -> Iterator[str]:
        yield from self._chunks


class FailingResponder:
    def stream_reply(self, conversation: Conversation, history: list[Message]) -> Iterator[str]:
        raise RuntimeError("model unavailable")
        yield  # pragma: no cover — make this a generator


def _make_app(responder: object):
    _app = create_app()
    conversation_repo = InMemoryConversationRepository()
    message_repo = InMemoryMessageRepository()
    _app.dependency_overrides[get_conversation_repository] = lambda: conversation_repo
    _app.dependency_overrides[get_message_repository] = lambda: message_repo
    _app.dependency_overrides[get_chatbot_responder] = lambda: responder
    return _app


def _parse_sse(body: str) -> list[tuple[str, dict]]:
    """Parse a Server-Sent Events stream into ``[(event, data_dict), ...]``."""
    events: list[tuple[str, dict]] = []
    for block in body.strip().split("\n\n"):
        if not block.strip():
            continue
        event_name = "message"
        data_lines: list[str] = []
        for line in block.splitlines():
            if line.startswith("event:"):
                event_name = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:") :].strip())
        if not data_lines:
            continue
        events.append((event_name, json.loads("\n".join(data_lines))))
    return events


@pytest.mark.anyio
async def test_post_message_does_not_trigger_bot_reply() -> None:
    """POST /messages persists only the user message; no bot reply is created."""
    _app = _make_app(responder=FakeStreamingResponder(["should-not-be-called"]))
    user_id = str(uuid.uuid4())
    headers = {"X-User-Id": user_id}

    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as client:
        created = await client.post(
            "/conversations",
            headers=headers,
            json={"title": "test", "display_name": "alice"},
        )
        assert created.status_code == 201
        conversation_id = created.json()["id"]

        posted = await client.post(
            f"/conversations/{conversation_id}/messages",
            headers=headers,
            json={"content": "hello"},
        )
        assert posted.status_code == 201
        assert posted.json()["role"] == "USER"

        messages = await client.get(f"/conversations/{conversation_id}/messages", headers=headers)
        assert messages.status_code == 200
        assert len(messages.json()) == 1
        assert messages.json()[0]["role"] == "USER"


@pytest.mark.anyio
async def test_agent_replies_streams_sse_events() -> None:
    """POST /agent-replies returns an SSE stream of delta + complete events."""
    chunks = ["こんに", "ちは", "！"]
    _app = _make_app(responder=FakeStreamingResponder(chunks))
    user_id = str(uuid.uuid4())
    headers = {"X-User-Id": user_id}

    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as client:
        created = await client.post(
            "/conversations",
            headers=headers,
            json={"title": "test", "display_name": "alice"},
        )
        conversation_id = created.json()["id"]

        await client.post(
            f"/conversations/{conversation_id}/messages",
            headers=headers,
            json={"content": "hello"},
        )

        reply = await client.post(
            f"/conversations/{conversation_id}/agent-replies",
            headers=headers,
        )
        assert reply.status_code == 200
        assert reply.headers["content-type"].startswith("text/event-stream")

        events = _parse_sse(reply.text)
        deltas = [data for name, data in events if name == "delta"]
        completes = [data for name, data in events if name == "complete"]

        assert [d["content"] for d in deltas] == chunks
        assert len(completes) == 1
        complete = completes[0]
        assert complete["role"] == "AGENT"
        assert complete["content"] == "".join(chunks)
        assert complete["conversation_id"] == conversation_id

        # The complete message should now be visible via GET /messages.
        messages = await client.get(f"/conversations/{conversation_id}/messages", headers=headers)
        roles = [m["role"] for m in messages.json()]
        assert "AGENT" in roles
        agent = next(m for m in messages.json() if m["role"] == "AGENT")
        assert agent["content"] == "".join(chunks)


@pytest.mark.anyio
async def test_agent_replies_emits_error_event_on_failure() -> None:
    """When the responder raises mid-stream, the SSE stream ends with an ``error`` event."""
    _app = _make_app(responder=FailingResponder())
    user_id = str(uuid.uuid4())
    headers = {"X-User-Id": user_id}

    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as client:
        created = await client.post(
            "/conversations",
            headers=headers,
            json={"title": "test"},
        )
        conversation_id = created.json()["id"]

        reply = await client.post(
            f"/conversations/{conversation_id}/agent-replies",
            headers=headers,
        )
        # The stream itself starts with 200 even on errors (headers go out first).
        assert reply.status_code == 200
        events = _parse_sse(reply.text)
        assert any(name == "error" for name, _ in events)


@pytest.mark.anyio
async def test_agent_replies_404_for_unknown_conversation() -> None:
    """Unknown ``conversation_id`` returns 404 before the stream begins."""
    _app = _make_app(responder=FakeStreamingResponder(["unused"]))
    user_id = str(uuid.uuid4())
    headers = {"X-User-Id": user_id}

    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as client:
        reply = await client.post(
            f"/conversations/{uuid.uuid4()}/agent-replies",
            headers=headers,
        )
        assert reply.status_code == 404


@pytest.mark.anyio
async def test_get_agents_returns_default_and_available() -> None:
    """GET /agents returns the configured default and the list of selectable types."""
    _app = _make_app(responder=FakeStreamingResponder([]))

    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as client:
        resp = await client.get("/agents")
        assert resp.status_code == 200
        body = resp.json()
        assert "default" in body
        assert isinstance(body.get("available"), list)
        # The configured default must always appear in the available list so
        # the UI can render it even when not currently usable.
        assert body["default"] in body["available"]
        # Built-in agents are always registered and selectable.
        for built_in in (AgentType.ECHO, AgentType.LANGGRAPH, AgentType.GITHUB_COPILOT_ECHO):
            assert built_in in body["available"]


@pytest.mark.anyio
async def test_agent_replies_accepts_agent_type_query_parameter() -> None:
    """POST /agent-replies?agent_type=<type> selects the per-request responder.

    The dependency override is keyed by function identity, not the runtime
    parameters, so the test verifies that the route still works when the
    ``agent_type`` query parameter is supplied. The actual selection logic is
    covered by ``create_chatbot_responder`` unit tests.
    """
    chunks = ["hi"]
    _app = _make_app(responder=FakeStreamingResponder(chunks))
    user_id = str(uuid.uuid4())
    headers = {"X-User-Id": user_id}

    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as client:
        created = await client.post(
            "/conversations",
            headers=headers,
            json={"title": "test"},
        )
        conversation_id = created.json()["id"]

        await client.post(
            f"/conversations/{conversation_id}/messages",
            headers=headers,
            json={"content": "hello"},
        )

        reply = await client.post(
            f"/conversations/{conversation_id}/agent-replies",
            headers=headers,
            params={"agent_type": AgentType.ECHO},
        )
        assert reply.status_code == 200
        events = _parse_sse(reply.text)
        assert any(name == "complete" for name, _ in events)
