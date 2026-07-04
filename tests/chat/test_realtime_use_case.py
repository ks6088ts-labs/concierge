"""Tests for StreamRealtimeVoiceUseCase."""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest

from concierge.chat.application.realtime_tools import RealtimeTool, build_capture_image_tool
from concierge.chat.application.responders import RealtimeVoiceSession
from concierge.chat.application.use_cases import (
    RealtimeCameraCaptureRequest,
    RealtimeMessagePersisted,
    RealtimeServerEvent,
    StreamRealtimeVoiceUseCase,
)
from concierge.chat.domain.entities import Conversation, Message
from concierge.chat.domain.exceptions import ConversationNotFoundError
from concierge.chat.domain.value_objects import MessageRole, Participant, ParticipantKind
from concierge.chat.infrastructure.persistence.memory import InMemoryConversationRepository, InMemoryMessageRepository

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeRealtimeSession:
    """In-memory session that yields pre-configured server events."""

    def __init__(self, server_events: list[dict]) -> None:  # type: ignore[type-arg]
        self._server_events = list(server_events)
        self.sent_events: list[dict] = []  # type: ignore[type-arg]
        self.closed = False

    def send_client_event(self, event: dict) -> None:  # type: ignore[type-arg]
        self.sent_events.append(event)

    def iter_server_events(self) -> Iterator[dict]:  # type: ignore[type-arg]
        yield from self._server_events

    def close(self) -> None:
        self.closed = True


class FakeRealtimeResponder:
    def __init__(self, server_events: list[dict]) -> None:  # type: ignore[type-arg]
        self._server_events = server_events
        self.last_session: FakeRealtimeSession | None = None

    def open(self, conversation: Conversation, history: list[Message]) -> RealtimeVoiceSession:
        self.last_session = FakeRealtimeSession(self._server_events)
        return self.last_session  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _user_participant(name: str = "alice") -> Participant:
    return Participant(id=uuid.uuid4(), kind=ParticipantKind.USER, display_name=name)


def _bot_participant() -> Participant:
    return Participant(
        id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        kind=ParticipantKind.AGENT,
        display_name="Concierge AI",
    )


def _make_use_case(
    server_events: list[dict],  # type: ignore[type-arg]
    *,
    conv_repo: InMemoryConversationRepository | None = None,
    msg_repo: InMemoryMessageRepository | None = None,
    tools: list[RealtimeTool] | None = None,
) -> tuple[
    StreamRealtimeVoiceUseCase,
    FakeRealtimeResponder,
    InMemoryConversationRepository,
    InMemoryMessageRepository,
]:
    conv_repo = conv_repo or InMemoryConversationRepository()
    msg_repo = msg_repo or InMemoryMessageRepository()
    responder = FakeRealtimeResponder(server_events)
    current = _user_participant()
    bot = _bot_participant()
    uc = StreamRealtimeVoiceUseCase(
        conversation_repository=conv_repo,
        message_repository=msg_repo,
        responder=responder,
        bot_participant=bot,
        current_participant=current,
        history_limit=20,
        tools=tools,
    )
    return uc, responder, conv_repo, msg_repo


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_conversation_not_found_raises() -> None:
    uc, _, _, _ = _make_use_case([])
    with pytest.raises(ConversationNotFoundError):
        list(uc.execute(uuid.uuid4()))


def test_client_event_is_forwarded() -> None:
    """send_client_event() forwards events to the session after execute()."""
    uc, responder, conv_repo, _ = _make_use_case([])
    from concierge.chat.application.use_cases import CreateConversationUseCase  # noqa: PLC0415

    conv = CreateConversationUseCase(conv_repo).execute("test", uc.current_participant)
    # Consume the (empty) iterator to open the session
    list(uc.execute(conv.id))
    assert responder.last_session is not None
    uc.send_client_event({"type": "input_audio_buffer.commit"})
    assert responder.last_session.sent_events == [{"type": "input_audio_buffer.commit"}]


def test_send_image_injects_input_image_item() -> None:
    """send_image() forwards a conversation.item.create with an input_image part."""
    uc, responder, conv_repo, _ = _make_use_case([])
    from concierge.chat.application.use_cases import CreateConversationUseCase  # noqa: PLC0415

    conv = CreateConversationUseCase(conv_repo).execute("test", uc.current_participant)
    list(uc.execute(conv.id))
    assert responder.last_session is not None

    data_url = "data:image/png;base64,iVBORw0KGgo="
    uc.send_image(data_url)

    items = [e for e in responder.last_session.sent_events if e.get("type") == "conversation.item.create"]
    assert len(items) == 1
    item = items[0]["item"]
    assert item["type"] == "message"
    assert item["role"] == "user"
    assert item["content"] == [{"type": "input_image", "image_url": data_url}]


def test_send_image_includes_optional_prompt() -> None:
    """An optional prompt is appended as an input_text content part."""
    uc, responder, conv_repo, _ = _make_use_case([])
    from concierge.chat.application.use_cases import CreateConversationUseCase  # noqa: PLC0415

    conv = CreateConversationUseCase(conv_repo).execute("test", uc.current_participant)
    list(uc.execute(conv.id))
    assert responder.last_session is not None

    data_url = "data:image/png;base64,iVBORw0KGgo="
    uc.send_image(data_url, prompt="これは何ですか?")

    items = [e for e in responder.last_session.sent_events if e.get("type") == "conversation.item.create"]
    assert items[0]["item"]["content"] == [
        {"type": "input_image", "image_url": data_url},
        {"type": "input_text", "text": "これは何ですか?"},
    ]


def test_send_image_without_session_is_noop() -> None:
    """Calling send_image() before execute() opens a session does not raise."""
    uc, _, _, _ = _make_use_case([])
    # No exception and nothing forwarded because no session exists yet.
    uc.send_image("data:image/png;base64,iVBORw0KGgo=")


def test_user_transcript_persisted() -> None:
    """USER transcript is saved when conversation.item.input_audio_transcription.completed arrives."""
    transcript_event = {
        "type": "conversation.item.input_audio_transcription.completed",
        "transcript": "こんにちは",
    }
    uc, _, conv_repo, msg_repo = _make_use_case([transcript_event])
    from concierge.chat.application.use_cases import CreateConversationUseCase  # noqa: PLC0415

    conv = CreateConversationUseCase(conv_repo).execute("test", uc.current_participant)
    events = list(uc.execute(conv.id))

    persisted = [e for e in events if isinstance(e, RealtimeMessagePersisted)]
    assert len(persisted) == 1
    msg = persisted[0].message
    assert msg.role == MessageRole.USER
    assert msg.content == "こんにちは"

    saved = msg_repo.find_by_conversation(conv.id, limit=10)
    assert any(m.content == "こんにちは" and m.role == MessageRole.USER for m in saved)


def test_agent_transcript_persisted() -> None:
    """AGENT transcript is saved when response.output_audio_transcript.done arrives."""
    transcript_event = {
        "type": "response.output_audio_transcript.done",
        "transcript": "はい、承知しました。",
    }
    uc, _, conv_repo, msg_repo = _make_use_case([transcript_event])
    from concierge.chat.application.use_cases import CreateConversationUseCase  # noqa: PLC0415

    conv = CreateConversationUseCase(conv_repo).execute("test", uc.current_participant)
    events = list(uc.execute(conv.id))

    persisted = [e for e in events if isinstance(e, RealtimeMessagePersisted)]
    assert len(persisted) == 1
    msg = persisted[0].message
    assert msg.role == MessageRole.AGENT
    assert msg.content == "はい、承知しました。"


def test_server_events_relayed_in_order() -> None:
    """All server events produce RealtimeServerEvent entries in the same order."""
    raw_events = [
        {"type": "response.output_audio.delta", "delta": "abc"},
        {"type": "response.output_audio.delta", "delta": "def"},
    ]
    uc, _, conv_repo, _ = _make_use_case(raw_events)
    from concierge.chat.application.use_cases import CreateConversationUseCase  # noqa: PLC0415

    conv = CreateConversationUseCase(conv_repo).execute("test", uc.current_participant)
    events = list(uc.execute(conv.id))

    server_events = [e for e in events if isinstance(e, RealtimeServerEvent)]
    assert len(server_events) == 2
    assert server_events[0].payload["delta"] == "abc"
    assert server_events[1].payload["delta"] == "def"


def test_mixed_events_order() -> None:
    """For transcript events: persisted notification comes before the raw relay."""
    user_transcript_event = {
        "type": "conversation.item.input_audio_transcription.completed",
        "transcript": "テスト",
    }
    uc, _, conv_repo, _ = _make_use_case([user_transcript_event])
    from concierge.chat.application.use_cases import CreateConversationUseCase  # noqa: PLC0415

    conv = CreateConversationUseCase(conv_repo).execute("test", uc.current_participant)
    events = list(uc.execute(conv.id))

    # Should have: RealtimeMessagePersisted + RealtimeServerEvent (in that order)
    assert len(events) == 2
    assert isinstance(events[0], RealtimeMessagePersisted)
    assert isinstance(events[1], RealtimeServerEvent)


def test_session_closed_after_relay() -> None:
    """The session is always closed after the relay completes."""
    uc, responder, conv_repo, _ = _make_use_case([])
    from concierge.chat.application.use_cases import CreateConversationUseCase  # noqa: PLC0415

    conv = CreateConversationUseCase(conv_repo).execute("test", uc.current_participant)
    list(uc.execute(conv.id))

    assert responder.last_session is not None
    assert responder.last_session.closed


def test_empty_transcript_not_persisted() -> None:
    """Events with an empty transcript string do not create messages."""
    events_in = [
        {"type": "conversation.item.input_audio_transcription.completed", "transcript": ""},
        {"type": "response.output_audio_transcript.done", "transcript": ""},
    ]
    uc, _, conv_repo, msg_repo = _make_use_case(events_in)
    from concierge.chat.application.use_cases import CreateConversationUseCase  # noqa: PLC0415

    conv = CreateConversationUseCase(conv_repo).execute("test", uc.current_participant)
    events = list(uc.execute(conv.id))

    persisted = [e for e in events if isinstance(e, RealtimeMessagePersisted)]
    assert persisted == []
    assert msg_repo.find_by_conversation(conv.id, limit=100) == []


# ---------------------------------------------------------------------------
# Tool calling
# ---------------------------------------------------------------------------


def _echo_tool() -> RealtimeTool:
    return RealtimeTool(
        name="echo",
        description="Echo the given text back.",
        parameters={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        handler=lambda args: f"echo:{args.get('text', '')}",
    )


def test_function_call_executes_tool_and_replies() -> None:
    """A function_call item runs the tool and feeds the result back to the session."""
    function_call_event = {
        "type": "response.output_item.done",
        "item": {
            "type": "function_call",
            "name": "echo",
            "call_id": "call_123",
            "arguments": '{"text": "hi"}',
        },
    }
    uc, responder, conv_repo, _ = _make_use_case([function_call_event], tools=[_echo_tool()])
    from concierge.chat.application.use_cases import CreateConversationUseCase  # noqa: PLC0415

    conv = CreateConversationUseCase(conv_repo).execute("test", uc.current_participant)
    list(uc.execute(conv.id))

    assert responder.last_session is not None
    sent = responder.last_session.sent_events
    # function_call_output carrying the tool result, then response.create
    output_event = next(e for e in sent if e.get("type") == "conversation.item.create")
    assert output_event["item"]["type"] == "function_call_output"
    assert output_event["item"]["call_id"] == "call_123"
    assert output_event["item"]["output"] == "echo:hi"
    assert any(e.get("type") == "response.create" for e in sent)


def test_unknown_function_call_returns_error_output() -> None:
    """An unknown tool still produces a function_call_output describing the error."""
    function_call_event = {
        "type": "response.output_item.done",
        "item": {
            "type": "function_call",
            "name": "does_not_exist",
            "call_id": "call_x",
            "arguments": "{}",
        },
    }
    uc, responder, conv_repo, _ = _make_use_case([function_call_event], tools=[_echo_tool()])
    from concierge.chat.application.use_cases import CreateConversationUseCase  # noqa: PLC0415

    conv = CreateConversationUseCase(conv_repo).execute("test", uc.current_participant)
    list(uc.execute(conv.id))

    assert responder.last_session is not None
    output_event = next(e for e in responder.last_session.sent_events if e.get("type") == "conversation.item.create")
    assert "error" in output_event["item"]["output"]


def test_function_call_ignored_when_no_tools_configured() -> None:
    """Without a tool registry, function_call items are relayed but not executed."""
    function_call_event = {
        "type": "response.output_item.done",
        "item": {"type": "function_call", "name": "echo", "call_id": "c", "arguments": "{}"},
    }
    uc, responder, conv_repo, _ = _make_use_case([function_call_event])
    from concierge.chat.application.use_cases import CreateConversationUseCase  # noqa: PLC0415

    conv = CreateConversationUseCase(conv_repo).execute("test", uc.current_participant)
    events = list(uc.execute(conv.id))

    assert responder.last_session is not None
    assert responder.last_session.sent_events == []
    assert any(isinstance(e, RealtimeServerEvent) for e in events)


# ---------------------------------------------------------------------------
# Hands-free camera (capture_image) tool
# ---------------------------------------------------------------------------


def test_capture_image_requests_browser_capture() -> None:
    """capture_image acknowledges the call and asks the browser to take a photo.

    It must NOT send response.create: the description is triggered later when the
    captured image is injected via send_image(trigger_response=True). Otherwise
    the model would speak before it can see the photo.
    """
    function_call_event = {
        "type": "response.output_item.done",
        "item": {
            "type": "function_call",
            "name": "capture_image",
            "call_id": "call_cam",
            "arguments": '{"prompt": "\u4f55\u304c\u898b\u3048\u308b?"}',
        },
    }
    uc, responder, conv_repo, _ = _make_use_case([function_call_event], tools=[build_capture_image_tool()])
    from concierge.chat.application.use_cases import CreateConversationUseCase  # noqa: PLC0415

    conv = CreateConversationUseCase(conv_repo).execute("test", uc.current_participant)
    events = list(uc.execute(conv.id))

    # The relay surfaces a camera-capture request carrying the optional prompt.
    capture_reqs = [e for e in events if isinstance(e, RealtimeCameraCaptureRequest)]
    assert len(capture_reqs) == 1
    assert capture_reqs[0].prompt == "\u4f55\u304c\u898b\u3048\u308b?"

    assert responder.last_session is not None
    sent = responder.last_session.sent_events
    output_event = next(e for e in sent if e.get("type") == "conversation.item.create")
    assert output_event["item"]["type"] == "function_call_output"
    assert output_event["item"]["call_id"] == "call_cam"
    # No response.create yet: the model waits for the image before describing it.
    assert all(e.get("type") != "response.create" for e in sent)


def test_capture_image_without_tool_registration_is_unknown() -> None:
    """capture_image is only honored when the capture tool was advertised.

    This prevents a default-mode session from opening the browser camera if the
    model hallucinates a tool name that was not in ``session.tools``.
    """
    function_call_event = {
        "type": "response.output_item.done",
        "item": {
            "type": "function_call",
            "name": "capture_image",
            "call_id": "call_cam",
            "arguments": "{}",
        },
    }
    uc, responder, conv_repo, _ = _make_use_case([function_call_event], tools=[_echo_tool()])
    from concierge.chat.application.use_cases import CreateConversationUseCase  # noqa: PLC0415

    conv = CreateConversationUseCase(conv_repo).execute("test", uc.current_participant)
    events = list(uc.execute(conv.id))

    assert not any(isinstance(e, RealtimeCameraCaptureRequest) for e in events)
    assert responder.last_session is not None
    sent = responder.last_session.sent_events
    output_event = next(e for e in sent if e.get("type") == "conversation.item.create")
    assert output_event["item"]["type"] == "function_call_output"
    assert "unknown tool" in output_event["item"]["output"]
    assert any(e.get("type") == "response.create" for e in sent)


def test_send_image_trigger_response_asks_for_reply() -> None:
    """send_image(trigger_response=True) injects the image then requests a reply."""
    uc, responder, conv_repo, _ = _make_use_case([])
    from concierge.chat.application.use_cases import CreateConversationUseCase  # noqa: PLC0415

    conv = CreateConversationUseCase(conv_repo).execute("test", uc.current_participant)
    list(uc.execute(conv.id))
    assert responder.last_session is not None

    uc.send_image("data:image/png;base64,iVBORw0KGgo=", trigger_response=True)
    sent = responder.last_session.sent_events
    assert sent[-2]["type"] == "conversation.item.create"
    assert sent[-2]["item"]["content"][0]["type"] == "input_image"
    assert sent[-1] == {"type": "response.create"}


def test_send_image_without_trigger_does_not_create_response() -> None:
    """The default send_image path stays silent so turn-taking is user-driven."""
    uc, responder, conv_repo, _ = _make_use_case([])
    from concierge.chat.application.use_cases import CreateConversationUseCase  # noqa: PLC0415

    conv = CreateConversationUseCase(conv_repo).execute("test", uc.current_participant)
    list(uc.execute(conv.id))
    assert responder.last_session is not None

    uc.send_image("data:image/png;base64,iVBORw0KGgo=")
    sent = responder.last_session.sent_events
    assert all(e.get("type") != "response.create" for e in sent)
