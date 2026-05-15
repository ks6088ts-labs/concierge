from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest

from concierge.chat.application.use_cases import (
    BotReplyComplete,
    BotReplyDelta,
    CreateConversationUseCase,
    GenerateBotReplyUseCase,
    PostMessageUseCase,
)
from concierge.chat.domain.entities import Conversation, Message
from concierge.chat.domain.exceptions import ConversationNotFoundError
from concierge.chat.domain.value_objects import MessageRole, Participant, ParticipantKind
from concierge.chat.infrastructure.persistence.memory import InMemoryConversationRepository, InMemoryMessageRepository


class FakeChatbotResponder:
    def __init__(self, chunks: list[str] | None = None) -> None:
        self.chunks = chunks if chunks is not None else ["Bot ", "reply"]
        self.received_history: list[Message] = []

    def stream_reply(self, conversation: Conversation, history: list[Message]) -> Iterator[str]:
        self.received_history = list(history)
        yield from self.chunks


def _user_participant(name: str = "alice") -> Participant:
    return Participant(id=uuid.uuid4(), kind=ParticipantKind.USER, display_name=name)


def _bot_participant() -> Participant:
    return Participant(
        id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        kind=ParticipantKind.AGENT,
        display_name="Concierge AI",
    )


def _collect(events: Iterator) -> tuple[list[BotReplyDelta], BotReplyComplete | None]:
    deltas: list[BotReplyDelta] = []
    final: BotReplyComplete | None = None
    for event in events:
        if isinstance(event, BotReplyDelta):
            deltas.append(event)
        elif isinstance(event, BotReplyComplete):
            final = event
    return deltas, final


def test_generate_bot_reply_happy_path() -> None:
    conversation_repo = InMemoryConversationRepository()
    message_repo = InMemoryMessageRepository()
    user = _user_participant()
    bot = _bot_participant()
    responder = FakeChatbotResponder(["こん", "にちは", "！"])

    conversation = CreateConversationUseCase(conversation_repo).execute("general", user)
    PostMessageUseCase(conversation_repo, message_repo).execute(conversation.id, user, "hello")

    use_case = GenerateBotReplyUseCase(conversation_repo, message_repo, responder, bot, history_limit=20)
    deltas, final = _collect(use_case.execute(conversation.id))

    assert [d.content for d in deltas] == ["こん", "にちは", "！"]
    assert final is not None
    assert final.message.role == MessageRole.AGENT
    assert final.message.content == "こんにちは！"
    assert final.message.sender.id == bot.id
    assert final.message.conversation_id == conversation.id

    # Verify the bot was added as participant
    updated_conversation = conversation_repo.find_by_id(conversation.id)
    assert updated_conversation is not None
    assert any(p.id == bot.id for p in updated_conversation.participants)

    # Verify the message was persisted
    persisted = message_repo.find_by_conversation(conversation.id)
    agent_messages = [m for m in persisted if m.role == MessageRole.AGENT]
    assert len(agent_messages) == 1


def test_generate_bot_reply_conversation_not_found() -> None:
    conversation_repo = InMemoryConversationRepository()
    message_repo = InMemoryMessageRepository()
    responder = FakeChatbotResponder()

    use_case = GenerateBotReplyUseCase(conversation_repo, message_repo, responder, _bot_participant())

    with pytest.raises(ConversationNotFoundError):
        # Validation must run before the iterator yields the first event.
        use_case.execute(uuid.uuid4())


def test_generate_bot_reply_history_limit() -> None:
    conversation_repo = InMemoryConversationRepository()
    message_repo = InMemoryMessageRepository()
    user = _user_participant()
    bot = _bot_participant()
    responder = FakeChatbotResponder(["reply"])

    conversation = CreateConversationUseCase(conversation_repo).execute("general", user)
    for i in range(5):
        PostMessageUseCase(conversation_repo, message_repo).execute(conversation.id, user, f"message {i}")

    use_case = GenerateBotReplyUseCase(conversation_repo, message_repo, responder, bot, history_limit=2)
    _collect(use_case.execute(conversation.id))

    # The responder should only receive at most history_limit messages
    assert len(responder.received_history) <= 2
