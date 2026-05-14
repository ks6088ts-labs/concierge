from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from concierge.chat.domain.entities import Conversation, Message
from concierge.chat.infrastructure.persistence.memory import InMemoryConversationRepository, InMemoryMessageRepository
from concierge.chat.infrastructure.web.app import create_app
from concierge.chat.infrastructure.web.dependencies import (
    get_chatbot_responder,
    get_conversation_repository,
    get_message_repository,
)
from concierge.chat.infrastructure.web.routes import get_bot_settings
from concierge.settings.chat import ChatSettings


class FakeChatbotResponder:
    def __init__(self, reply: str = "Bot reply") -> None:
        self.reply = reply

    def generate_reply(self, conversation: Conversation, history: list[Message]) -> str:
        return self.reply


class NullResponder:
    def generate_reply(self, conversation: Conversation, history: list[Message]) -> str:
        from concierge.chat.infrastructure.ai.null_responder import ChatbotDisabledError

        raise ChatbotDisabledError("Chatbot is disabled")


def _make_app(*, bot_enabled: bool, responder: object):
    _app = create_app()
    conversation_repo = InMemoryConversationRepository()
    message_repo = InMemoryMessageRepository()
    _app.dependency_overrides[get_conversation_repository] = lambda: conversation_repo
    _app.dependency_overrides[get_message_repository] = lambda: message_repo
    _app.dependency_overrides[get_chatbot_responder] = lambda: responder
    _app.dependency_overrides[get_bot_settings] = lambda: ChatSettings(bot_enabled=bot_enabled)
    return _app


@pytest.mark.anyio
async def test_post_message_auto_reply_enabled() -> None:
    """When bot is enabled, POST /messages triggers bot reply; GET /messages returns 2 messages."""
    _app = _make_app(bot_enabled=True, responder=FakeChatbotResponder("AIの返事"))
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
        # The immediate response is still the user's message
        assert posted.json()["role"] == "USER"

        messages = await client.get(f"/conversations/{conversation_id}/messages", headers=headers)
        assert messages.status_code == 200
        msg_list = messages.json()
        # Should have user message + bot reply
        assert len(msg_list) == 2
        roles = {m["role"] for m in msg_list}
        assert "USER" in roles
        assert "AGENT" in roles


@pytest.mark.anyio
async def test_agent_reply_endpoint_enabled() -> None:
    """POST /agent-replies with bot enabled returns 201 + AGENT MessageResponse."""
    _app = _make_app(bot_enabled=True, responder=FakeChatbotResponder("AIの返事"))
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

        await client.post(
            f"/conversations/{conversation_id}/messages",
            headers=headers,
            json={"content": "hello"},
        )

        reply = await client.post(
            f"/conversations/{conversation_id}/agent-replies",
            headers=headers,
        )
        assert reply.status_code == 201
        data = reply.json()
        assert data["role"] == "AGENT"
        assert data["content"] == "AIの返事"


@pytest.mark.anyio
async def test_agent_reply_endpoint_disabled() -> None:
    """POST /agent-replies with bot disabled returns 409 Conflict."""
    _app = _make_app(bot_enabled=False, responder=NullResponder())
    user_id = str(uuid.uuid4())
    headers = {"X-User-Id": user_id}

    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as client:
        created = await client.post(
            "/conversations",
            headers=headers,
            json={"title": "test"},
        )
        assert created.status_code == 201
        conversation_id = created.json()["id"]

        reply = await client.post(
            f"/conversations/{conversation_id}/agent-replies",
            headers=headers,
        )
        assert reply.status_code == 409


@pytest.mark.anyio
async def test_post_message_bot_disabled_schema_unchanged() -> None:
    """When bot is disabled (default), POST /messages response schema is unchanged and no bot message is saved."""
    _app = _make_app(bot_enabled=False, responder=NullResponder())
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
            json={"content": "hello", "display_name": "alice"},
        )
        assert posted.status_code == 201
        data = posted.json()
        # Schema must include these fields, unchanged
        assert "id" in data
        assert "conversation_id" in data
        assert "sender" in data
        assert "role" in data
        assert "content" in data
        assert "created_at" in data
        assert data["role"] == "USER"

        messages = await client.get(f"/conversations/{conversation_id}/messages", headers=headers)
        assert messages.status_code == 200
        # Only the user message, no bot reply
        assert len(messages.json()) == 1
