from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from concierge.chat.infrastructure.persistence.memory import InMemoryConversationRepository, InMemoryMessageRepository
from concierge.chat.infrastructure.web.app import create_app
from concierge.chat.infrastructure.web.dependencies import (
    get_conversation_repository,
    get_message_repository,
)


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


@pytest.mark.anyio
async def test_realtime_path_redirects_to_root(app) -> None:
    """``/realtime`` is kept for backward compatibility but now redirects to ``/``.

    The dedicated realtime UI has been merged into the main chat page.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/realtime")
        assert resp.status_code == 301
        assert resp.headers["location"] == "/"


@pytest.mark.anyio
async def test_accessible_page_served(app) -> None:
    """The ``/accessible`` route serves the minimal deafblind UI, not the full chat."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/accessible")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        body = resp.text
        # It is the stripped-down accessible page with a single dialogue region…
        assert 'id="dialogue"' in body
        assert "アクセシブル" in body
        # …and none of the conversation-list / new-conversation chrome a web
        # reader would otherwise have to wade through.
        assert "新しい会話" not in body


@pytest.mark.anyio
async def test_accessible_config_reports_rate_and_realtime(app, monkeypatch) -> None:
    """``/accessible/config`` reports realtime availability, the TTS rate, and transcription."""
    monkeypatch.setenv("AZURE_AI_PROJECT_ENDPOINT_REALTIME", "")
    monkeypatch.setenv("CHAT_REALTIME_TRANSCRIPTION_MODEL", "")
    from concierge.settings import get_chat_settings, get_microsoft_foundry_settings  # noqa: PLC0415

    get_microsoft_foundry_settings.cache_clear()
    get_chat_settings.cache_clear()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/accessible/config")
        assert resp.status_code == 200
        body = resp.json()
        assert body["realtime"] is False
        assert isinstance(body["tts_rate"], int | float)
        assert body["tts_rate"] > 0
        # No transcription model configured → the accessible UI shows the
        # "self-transcription is off" notice.
        assert body["transcription"] is False

    get_microsoft_foundry_settings.cache_clear()
    get_chat_settings.cache_clear()


@pytest.mark.anyio
async def test_accessible_config_reports_transcription_enabled(app, monkeypatch) -> None:
    """``transcription`` is True when ``CHAT_REALTIME_TRANSCRIPTION_MODEL`` is set."""
    monkeypatch.setenv("CHAT_REALTIME_TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe")
    from concierge.settings import get_chat_settings  # noqa: PLC0415

    get_chat_settings.cache_clear()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/accessible/config")
        assert resp.status_code == 200
        assert resp.json()["transcription"] is True

    get_chat_settings.cache_clear()


@pytest.mark.anyio
async def test_capabilities_reports_realtime_disabled(app, monkeypatch) -> None:
    """When ``AZURE_AI_PROJECT_ENDPOINT_REALTIME`` is empty, ``realtime`` is False."""
    # Explicit empty string overrides the developer's local ``.env`` (which
    # pydantic-settings reads as a fallback when the env var is missing).
    monkeypatch.setenv("AZURE_AI_PROJECT_ENDPOINT_REALTIME", "")
    from concierge.settings import get_microsoft_foundry_settings  # noqa: PLC0415

    get_microsoft_foundry_settings.cache_clear()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/capabilities")
        assert resp.status_code == 200
        assert resp.json() == {"realtime": False}

    get_microsoft_foundry_settings.cache_clear()


@pytest.mark.anyio
async def test_capabilities_reports_realtime_enabled(app, monkeypatch) -> None:
    """When the realtime endpoint env var is set, ``realtime`` is True."""
    monkeypatch.setenv("AZURE_AI_PROJECT_ENDPOINT_REALTIME", "https://example.openai.azure.com/")
    from concierge.settings import get_microsoft_foundry_settings  # noqa: PLC0415

    get_microsoft_foundry_settings.cache_clear()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/capabilities")
        assert resp.status_code == 200
        assert resp.json() == {"realtime": True}

    get_microsoft_foundry_settings.cache_clear()
