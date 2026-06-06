from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime

from concierge.chat.application.realtime_tools import RealtimeTool
from concierge.chat.application.repositories import ConversationRepository, MessageRepository
from concierge.chat.application.responders import ChatbotResponder, RealtimeVoiceResponder
from concierge.chat.domain.entities import Conversation, Message
from concierge.chat.domain.exceptions import ConversationNotFoundError, MessageValidationError
from concierge.chat.domain.value_objects import MessageRole, Participant

logger = logging.getLogger(__name__)


class CreateConversationUseCase:
    def __init__(self, conversation_repository: ConversationRepository):
        self.conversation_repository = conversation_repository

    def execute(self, title: str, creator: Participant) -> Conversation:
        conversation = Conversation(title=title, participants=[creator])
        created = self.conversation_repository.save(conversation)
        logger.info("Created conversation id=%s", created.id)
        return created


class GetConversationUseCase:
    def __init__(self, conversation_repository: ConversationRepository):
        self.conversation_repository = conversation_repository

    def execute(self, conversation_id: uuid.UUID) -> Conversation:
        conversation = self.conversation_repository.find_by_id(conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(conversation_id)
        return conversation


class ListConversationsUseCase:
    def __init__(self, conversation_repository: ConversationRepository):
        self.conversation_repository = conversation_repository

    def execute(self, participant_id: uuid.UUID | None = None) -> list[Conversation]:
        return self.conversation_repository.find_all(participant_id=participant_id)


class JoinConversationUseCase:
    def __init__(self, conversation_repository: ConversationRepository):
        self.conversation_repository = conversation_repository

    def execute(self, conversation_id: uuid.UUID, participant: Participant) -> Conversation:
        conversation = self.conversation_repository.find_by_id(conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(conversation_id)
        conversation.add_participant(participant)
        updated = self.conversation_repository.save(conversation)
        logger.info("Joined conversation id=%s participant=%s", updated.id, participant.id)
        return updated


class PostMessageUseCase:
    def __init__(self, conversation_repository: ConversationRepository, message_repository: MessageRepository):
        self.conversation_repository = conversation_repository
        self.message_repository = message_repository

    def execute(self, conversation_id: uuid.UUID, sender: Participant, content: str) -> Message:
        conversation = self.conversation_repository.find_by_id(conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(conversation_id)
        if all(participant.id != sender.id for participant in conversation.participants):
            raise MessageValidationError("sender is not a participant in this conversation")
        message = Message(conversation_id=conversation_id, sender=sender, content=content)
        created = self.message_repository.save(message)
        logger.info("Posted message id=%s", created.id)
        return created


class ListMessagesUseCase:
    def __init__(self, conversation_repository: ConversationRepository, message_repository: MessageRepository):
        self.conversation_repository = conversation_repository
        self.message_repository = message_repository

    def execute(
        self,
        conversation_id: uuid.UUID,
        *,
        limit: int = 100,
        before: datetime | None = None,
    ) -> list[Message]:
        if self.conversation_repository.find_by_id(conversation_id) is None:
            raise ConversationNotFoundError(conversation_id)
        return self.message_repository.find_by_conversation(conversation_id, limit=limit, before=before)


class DeleteConversationUseCase:
    def __init__(self, conversation_repository: ConversationRepository, message_repository: MessageRepository):
        self.conversation_repository = conversation_repository
        self.message_repository = message_repository

    def execute(self, conversation_id: uuid.UUID) -> None:
        if self.conversation_repository.find_by_id(conversation_id) is None:
            raise ConversationNotFoundError(conversation_id)
        deleted_messages = self.message_repository.delete_by_conversation(conversation_id)
        self.conversation_repository.delete(conversation_id)
        logger.info("Deleted conversation id=%s messages=%s", conversation_id, deleted_messages)


class GenerateBotReplyUseCase:
    """Stream an AI bot reply for a conversation.

    ``execute()`` performs synchronous validation (conversation existence) and
    returns an iterator that yields :class:`BotReplyEvent` values. Validation
    errors propagate before the iterator starts so that transport layers can
    map them to HTTP errors via the regular exception handlers.
    """

    def __init__(
        self,
        conversation_repository: ConversationRepository,
        message_repository: MessageRepository,
        responder: ChatbotResponder,
        bot_participant: Participant,
        history_limit: int = 20,
    ):
        self.conversation_repository = conversation_repository
        self.message_repository = message_repository
        self.responder = responder
        self.bot_participant = bot_participant
        self.history_limit = history_limit

    def execute(self, conversation_id: uuid.UUID) -> Iterator[BotReplyEvent]:
        conversation = self.conversation_repository.find_by_id(conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(conversation_id)
        history = self.message_repository.find_by_conversation(conversation_id, limit=self.history_limit)
        conversation.add_participant(self.bot_participant)
        self.conversation_repository.save(conversation)
        return self._stream(conversation, history, conversation_id)

    def _stream(
        self,
        conversation: Conversation,
        history: list[Message],
        conversation_id: uuid.UUID,
    ) -> Iterator[BotReplyEvent]:
        chunks: list[str] = []
        for chunk in self.responder.stream_reply(conversation, history):
            if not chunk:
                continue
            chunks.append(chunk)
            yield BotReplyDelta(content=chunk)
        message = Message(
            conversation_id=conversation_id,
            sender=self.bot_participant,
            content="".join(chunks),
            role=MessageRole.AGENT,
        )
        saved = self.message_repository.save(message)
        logger.info("Bot replied message id=%s in conversation=%s", saved.id, conversation_id)
        yield BotReplyComplete(message=saved)


@dataclass(frozen=True)
class BotReplyDelta:
    """Incremental text chunk emitted while the bot is generating."""

    content: str


@dataclass(frozen=True)
class BotReplyComplete:
    """Terminal event carrying the persisted :class:`Message`."""

    message: Message


BotReplyEvent = BotReplyDelta | BotReplyComplete


class StreamRealtimeVoiceUseCase:
    """Relay bidirectional voice events between a browser client and the upstream model.

    Responsibilities:
    1. Validate ``conversation_id`` existence.
    2. Load history and ensure the bot participant is joined.
    3. Open a :class:`RealtimeVoiceSession` and relay events transparently.
    4. Capture ``conversation.item.input_audio_transcription.completed`` and
       ``response.audio_transcript.done`` server events to persist transcripts
       as :class:`Message` objects.
    5. Yield :class:`RealtimeServerEvent`, :class:`RealtimeMessagePersisted`,
       and :class:`RealtimeError` to the caller (web route).
    """

    def __init__(
        self,
        conversation_repository: ConversationRepository,
        message_repository: MessageRepository,
        responder: RealtimeVoiceResponder,
        bot_participant: Participant,
        current_participant: Participant,
        history_limit: int = 20,
        tools: list[RealtimeTool] | None = None,
    ):
        self.conversation_repository = conversation_repository
        self.message_repository = message_repository
        self.responder = responder
        self.bot_participant = bot_participant
        self.current_participant = current_participant
        self.history_limit = history_limit
        self._tools = {tool.name: tool for tool in tools or []}

    def execute(self, conversation_id: uuid.UUID) -> Iterator[RealtimeEvent]:
        conversation = self.conversation_repository.find_by_id(conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(conversation_id)
        history = self.message_repository.find_by_conversation(conversation_id, limit=self.history_limit)
        conversation.add_participant(self.bot_participant)
        self.conversation_repository.save(conversation)
        self._session = self.responder.open(conversation, history)
        return self._relay(self._session, conversation_id)

    def send_client_event(self, event: dict) -> None:  # type: ignore[type-arg]
        """Forward a client event to the upstream session."""
        if hasattr(self, "_session") and self._session is not None:
            self._session.send_client_event(event)

    def _relay(self, session, conversation_id: uuid.UUID) -> Iterator[RealtimeEvent]:  # type: ignore[type-arg]
        try:
            for server_event in session.iter_server_events():
                event_type = server_event.get("type", "")

                # Persist USER transcript
                if event_type == "conversation.item.input_audio_transcription.completed":
                    transcript = server_event.get("transcript", "")
                    if transcript:
                        msg = Message(
                            conversation_id=conversation_id,
                            sender=self.current_participant,
                            content=transcript,
                            role=MessageRole.USER,
                        )
                        saved = self.message_repository.save(msg)
                        logger.info("Persisted USER transcript id=%s", saved.id)
                        yield RealtimeMessagePersisted(message=saved)

                # Persist AGENT transcript
                # Note: GA endpoint emits ``response.output_audio_transcript.done``
                # (the preview endpoint used ``response.audio_transcript.done``).
                elif event_type == "response.output_audio_transcript.done":
                    transcript = server_event.get("transcript", "")
                    if transcript:
                        msg = Message(
                            conversation_id=conversation_id,
                            sender=self.bot_participant,
                            content=transcript,
                            role=MessageRole.AGENT,
                        )
                        saved = self.message_repository.save(msg)
                        logger.info("Persisted AGENT transcript id=%s", saved.id)
                        yield RealtimeMessagePersisted(message=saved)

                # Execute a tool the model asked for, then let it continue.
                # Foundry surfaces a completed ``function_call`` item via
                # ``response.output_item.done`` (containing name, call_id and the
                # full arguments JSON).
                elif event_type == "response.output_item.done":
                    item = server_event.get("item") or {}
                    if self._tools and item.get("type") == "function_call":
                        self._handle_function_call(session, item)

                # Always relay the raw server event to the browser
                yield RealtimeServerEvent(payload=server_event)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Realtime relay error in conversation %s", conversation_id)
            yield RealtimeError(detail=str(exc))
        finally:
            session.close()

    def _handle_function_call(self, session, item: dict) -> None:  # type: ignore[type-arg]
        """Run a model-requested tool and feed the result back to the session."""
        name = item.get("name", "")
        call_id = item.get("call_id", "")
        raw_args = item.get("arguments") or "{}"
        try:
            arguments = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
        except (json.JSONDecodeError, TypeError):
            arguments = {}

        logger.info(
            "Realtime tool call requested name=%s call_id=%s arguments=%s",
            name,
            call_id,
            arguments,
        )

        tool = self._tools.get(name)
        if tool is None:
            logger.warning("Realtime tool call for unknown tool name=%s call_id=%s", name, call_id)
            output = json.dumps({"error": f"unknown tool: {name!r}"})
        else:
            try:
                output = tool.handler(arguments)
                logger.info(
                    "Realtime tool call succeeded name=%s call_id=%s output=%s",
                    name,
                    call_id,
                    output,
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Realtime tool call failed name=%s call_id=%s", name, call_id)
                output = json.dumps({"error": str(exc)})

        session.send_client_event(
            {
                "type": "conversation.item.create",
                "item": {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": output,
                },
            }
        )
        # Ask the model to continue now that the tool result is in context.
        session.send_client_event({"type": "response.create"})


# ---------------------------------------------------------------------------
# Realtime event types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RealtimeServerEvent:
    """Raw JSON event from Foundry to be forwarded to the browser."""

    payload: dict  # type: ignore[type-arg]


@dataclass(frozen=True)
class RealtimeMessagePersisted:
    """Emitted after a transcript has been saved to the message repository."""

    message: Message


@dataclass(frozen=True)
class RealtimeError:
    """Emitted when the relay encounters an unhandled exception."""

    detail: str


RealtimeEvent = RealtimeServerEvent | RealtimeMessagePersisted | RealtimeError
