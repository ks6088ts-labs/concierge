from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from concierge.chat.infrastructure.persistence.memory import InMemoryConversationRepository, InMemoryMessageRepository
from concierge.chat.infrastructure.web.app import create_app
from concierge.chat.infrastructure.web.dependencies import get_conversation_repository, get_message_repository


@pytest.fixture
def app():
    app = create_app()
    conversation_repo = InMemoryConversationRepository()
    message_repo = InMemoryMessageRepository()
    app.dependency_overrides[get_conversation_repository] = lambda: conversation_repo
    app.dependency_overrides[get_message_repository] = lambda: message_repo
    return app


@pytest.mark.anyio
async def test_api_endpoints(app) -> None:
    user_id = str(uuid.uuid4())
    headers = {"X-User-Id": user_id}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        health = await client.get("/healthz")
        assert health.status_code == 200

        created = await client.post(
            "/conversations",
            headers=headers,
            json={"title": "general", "display_name": "alice"},
        )
        assert created.status_code == 201
        conversation_id = created.json()["id"]

        listed = await client.get("/conversations", headers=headers, params={"mine": "true"})
        assert listed.status_code == 200
        assert len(listed.json()) == 1

        joined = await client.post(
            f"/conversations/{conversation_id}/participants",
            headers=headers,
            json={"display_name": "alice"},
        )
        assert joined.status_code == 200

        posted = await client.post(
            f"/conversations/{conversation_id}/messages",
            headers=headers,
            json={"content": "hello", "display_name": "alice"},
        )
        assert posted.status_code == 201

        messages = await client.get(f"/conversations/{conversation_id}/messages", headers=headers)
        assert messages.status_code == 200
        assert len(messages.json()) == 1

        deleted = await client.delete(f"/conversations/{conversation_id}", headers=headers)
        assert deleted.status_code == 204


@pytest.mark.anyio
async def test_api_validation_and_not_found(app) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        missing_header = await client.post("/conversations", json={"title": "general"})
        assert missing_header.status_code == 422

        invalid_header = await client.post(
            "/conversations",
            headers={"X-User-Id": "invalid"},
            json={"title": "general"},
        )
        assert invalid_header.status_code == 422

        not_found = await client.get(f"/conversations/{uuid.uuid4()}", headers={"X-User-Id": str(uuid.uuid4())})
        assert not_found.status_code == 404

        invalid_body = await client.post(
            "/conversations",
            headers={"X-User-Id": str(uuid.uuid4())},
            json={"title": ""},
        )
        assert invalid_body.status_code == 422
