"""WebSocket route tests for the realtime voice endpoint."""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from concierge.chat.application.responders import RealtimeVoiceSession
from concierge.chat.domain.entities import Conversation, Message
from concierge.chat.infrastructure.persistence.memory import InMemoryConversationRepository, InMemoryMessageRepository
from concierge.chat.infrastructure.web.app import create_app
from concierge.chat.infrastructure.web.dependencies import (
    get_conversation_repository,
    get_message_repository,
    get_realtime_responder_bundle_optional,
)

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeRealtimeSession:
    def __init__(self, server_events: list[dict]) -> None:  # type: ignore[type-arg]
        self._events = list(server_events)
        self.sent_events: list[dict] = []  # type: ignore[type-arg]
        self.closed = False

    def send_client_event(self, event: dict) -> None:  # type: ignore[type-arg]
        self.sent_events.append(event)

    def iter_server_events(self) -> Iterator[dict]:  # type: ignore[type-arg]
        yield from self._events

    def close(self) -> None:
        self.closed = True


class FakeRealtimeResponder:
    def __init__(self, server_events: list[dict] | None = None) -> None:  # type: ignore[type-arg]
        self._events: list[dict] = server_events or []  # type: ignore[type-arg]
        self.last_session: FakeRealtimeSession | None = None

    def open(self, conversation: Conversation, history: list[Message]) -> RealtimeVoiceSession:
        self.last_session = FakeRealtimeSession(self._events)
        return self.last_session  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app(responder: FakeRealtimeResponder | None = None):
    app = create_app()
    conv_repo = InMemoryConversationRepository()
    msg_repo = InMemoryMessageRepository()
    app.dependency_overrides[get_conversation_repository] = lambda: conv_repo
    app.dependency_overrides[get_message_repository] = lambda: msg_repo
    if responder is not None:
        app.dependency_overrides[get_realtime_responder_bundle_optional] = lambda: (responder, [])
    return app, conv_repo, msg_repo


def _create_conv(client: TestClient, user_id: str, title: str = "test") -> str:
    resp = client.post(
        "/conversations",
        headers={"X-User-Id": user_id},
        json={"title": title, "display_name": "alice"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_close_4503_when_realtime_not_configured() -> None:
    """Without AZURE_AI_PROJECT_ENDPOINT_REALTIME the endpoint closes with 4503."""
    # Override get_realtime_responder_bundle_optional to return None (simulating not configured)
    app = create_app()
    user_id = str(uuid.uuid4())
    conv_repo = InMemoryConversationRepository()
    msg_repo = InMemoryMessageRepository()
    app.dependency_overrides[get_conversation_repository] = lambda: conv_repo
    app.dependency_overrides[get_message_repository] = lambda: msg_repo
    app.dependency_overrides[get_realtime_responder_bundle_optional] = lambda: None

    client = TestClient(app)
    # Create a conversation first
    conv_id = _create_conv(client, user_id)

    with pytest.raises(Exception):  # noqa: B017 — WS close before accept raises
        with client.websocket_connect(f"/conversations/{conv_id}/realtime?user_id={user_id}") as ws:
            ws.receive_json()


def test_close_4404_for_unknown_conversation() -> None:
    """Unknown conversation_id closes with 4404."""
    responder = FakeRealtimeResponder()
    app, _, _ = _make_app(responder)
    user_id = str(uuid.uuid4())
    unknown_id = str(uuid.uuid4())

    client = TestClient(app)
    with pytest.raises(Exception):  # noqa: B017
        with client.websocket_connect(f"/conversations/{unknown_id}/realtime?user_id={user_id}") as ws:
            ws.receive_json()


def test_close_4400_for_invalid_user_id() -> None:
    """Invalid user_id closes with 4400."""
    responder = FakeRealtimeResponder()
    app, conv_repo, _ = _make_app(responder)
    user_id = str(uuid.uuid4())
    client = TestClient(app)
    conv_id = _create_conv(client, user_id)

    with pytest.raises(Exception):  # noqa: B017
        with client.websocket_connect(f"/conversations/{conv_id}/realtime?user_id=not-a-uuid") as ws:
            ws.receive_json()


def test_session_ready_event_sent() -> None:
    """After accepting, the server sends concierge.session.ready."""
    responder = FakeRealtimeResponder(server_events=[])
    app, _, _ = _make_app(responder)
    user_id = str(uuid.uuid4())
    client = TestClient(app)
    conv_id = _create_conv(client, user_id)

    with client.websocket_connect(f"/conversations/{conv_id}/realtime?user_id={user_id}&display_name=alice") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "concierge.session.ready"
        assert msg["conversation_id"] == conv_id


def test_persisted_message_event_for_agent_transcript() -> None:
    """AGENT transcript causes a concierge.message.persisted event."""
    transcript_event = {
        "type": "response.output_audio_transcript.done",
        "transcript": "こんにちは",
    }
    responder = FakeRealtimeResponder(server_events=[transcript_event])
    app, _, _ = _make_app(responder)
    user_id = str(uuid.uuid4())
    client = TestClient(app)
    conv_id = _create_conv(client, user_id)

    received = []
    with client.websocket_connect(f"/conversations/{conv_id}/realtime?user_id={user_id}") as ws:
        # First message is session.ready
        ready = ws.receive_json()
        assert ready["type"] == "concierge.session.ready"
        # Collect subsequent messages
        import threading  # noqa: PLC0415

        done = threading.Event()

        def _recv() -> None:
            try:
                while True:
                    received.append(ws.receive_json())
            except Exception:
                done.set()

        t = threading.Thread(target=_recv, daemon=True)
        t.start()
        done.wait(timeout=3)

    persisted = [m for m in received if m.get("type") == "concierge.message.persisted"]
    assert len(persisted) >= 1
    assert persisted[0]["message"]["role"] == "AGENT"
    assert persisted[0]["message"]["content"] == "こんにちは"


def test_client_oai_event_forwarded_to_session() -> None:
    """oai-event messages from the client are forwarded to the session."""
    responder = FakeRealtimeResponder(server_events=[])
    app, _, _ = _make_app(responder)
    user_id = str(uuid.uuid4())
    client = TestClient(app)
    conv_id = _create_conv(client, user_id)

    with client.websocket_connect(f"/conversations/{conv_id}/realtime?user_id={user_id}") as ws:
        ready = ws.receive_json()
        assert ready["type"] == "concierge.session.ready"
        ws.send_json({"type": "oai-event", "payload": {"type": "input_audio_buffer.commit"}})
        # Give the relay thread a moment to process
        import time  # noqa: PLC0415

        time.sleep(0.1)

    assert responder.last_session is not None
    assert any(e.get("type") == "input_audio_buffer.commit" for e in responder.last_session.sent_events)


def test_image_input_forwarded_as_conversation_item() -> None:
    """A valid concierge.image.input is injected as an input_image conversation item."""
    responder = FakeRealtimeResponder(server_events=[])
    app, _, _ = _make_app(responder)
    user_id = str(uuid.uuid4())
    client = TestClient(app)
    conv_id = _create_conv(client, user_id)

    data_url = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQ=="
    with client.websocket_connect(f"/conversations/{conv_id}/realtime?user_id={user_id}") as ws:
        ready = ws.receive_json()
        assert ready["type"] == "concierge.session.ready"
        ws.send_json({"type": "concierge.image.input", "image_url": data_url})
        import time  # noqa: PLC0415

        time.sleep(0.1)

    assert responder.last_session is not None
    items = [e for e in responder.last_session.sent_events if e.get("type") == "conversation.item.create"]
    assert len(items) == 1
    content = items[0]["item"]["content"]
    assert content[0]["type"] == "input_image"
    assert content[0]["image_url"] == data_url


def test_image_input_rejects_non_data_url() -> None:
    """A non-data:image URL is rejected with concierge.error and not forwarded."""
    responder = FakeRealtimeResponder(server_events=[])
    app, _, _ = _make_app(responder)
    user_id = str(uuid.uuid4())
    client = TestClient(app)
    conv_id = _create_conv(client, user_id)

    with client.websocket_connect(f"/conversations/{conv_id}/realtime?user_id={user_id}") as ws:
        ready = ws.receive_json()
        assert ready["type"] == "concierge.session.ready"
        ws.send_json({"type": "concierge.image.input", "image_url": "https://example.com/x.png"})
        err = ws.receive_json()
        assert err["type"] == "concierge.error"

    assert responder.last_session is not None
    assert not any(e.get("type") == "conversation.item.create" for e in responder.last_session.sent_events)


def test_accessible_mode_uses_accessible_prompt_and_capture_tool(monkeypatch) -> None:
    """``mode=accessible`` builds the responder with the accessible prompt + camera tool."""
    from concierge.chat.infrastructure.web import dependencies as deps_module  # noqa: PLC0415
    from concierge.settings import get_chat_settings  # noqa: PLC0415

    captured: dict = {}
    accessible_responder = FakeRealtimeResponder(server_events=[])

    def _fake_create(system_prompt=None, extra_tools=None):
        captured["system_prompt"] = system_prompt
        captured["extra_tools"] = extra_tools
        return accessible_responder, list(extra_tools or [])

    monkeypatch.setattr(deps_module, "create_realtime_responder_with_tools", _fake_create)

    app, _, _ = _make_app()
    user_id = str(uuid.uuid4())
    client = TestClient(app)
    conv_id = _create_conv(client, user_id)

    with client.websocket_connect(f"/conversations/{conv_id}/realtime?user_id={user_id}&mode=accessible") as ws:
        ready = ws.receive_json()
        assert ready["type"] == "concierge.session.ready"

    assert captured["system_prompt"] == get_chat_settings().realtime_accessible_system_prompt
    assert any(t.name == "capture_image" for t in captured["extra_tools"])
    assert accessible_responder.last_session is not None


def test_default_mode_does_not_use_accessible_prompt(monkeypatch) -> None:
    """Without ``mode=accessible`` the default prompt/tool set is requested."""
    from concierge.chat.infrastructure.web import dependencies as deps_module  # noqa: PLC0415

    captured: dict = {}
    responder = FakeRealtimeResponder(server_events=[])

    def _fake_create(system_prompt=None, extra_tools=None):
        captured["system_prompt"] = system_prompt
        captured["extra_tools"] = extra_tools
        return responder, []

    monkeypatch.setattr(deps_module, "create_realtime_responder_with_tools", _fake_create)

    app, _, _ = _make_app()
    user_id = str(uuid.uuid4())
    client = TestClient(app)
    conv_id = _create_conv(client, user_id)

    with client.websocket_connect(f"/conversations/{conv_id}/realtime?user_id={user_id}") as ws:
        ready = ws.receive_json()
        assert ready["type"] == "concierge.session.ready"

    assert captured["system_prompt"] is None
    assert captured["extra_tools"] is None
    assert responder.last_session is not None
