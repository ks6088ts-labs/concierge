from __future__ import annotations

import uuid

import pytest

from concierge.chat.application.use_cases import CreateConversationUseCase, GenerateBotReplyUseCase, PostMessageUseCase
from concierge.chat.domain.entities import Conversation, Message
from concierge.chat.domain.exceptions import ConversationNotFoundError
from concierge.chat.domain.value_objects import MessageRole, Participant, ParticipantKind
from concierge.chat.infrastructure.persistence.memory import InMemoryConversationRepository, InMemoryMessageRepository


class FakeChatbotResponder:
    def __init__(self, reply: str = "Bot reply") -> None:
        self.reply = reply
        self.received_history: list[Message] = []

    def generate_reply(self, conversation: Conversation, history: list[Message]) -> str:
        self.received_history = list(history)
        return self.reply


def _user_participant(name: str = "alice") -> Participant:
    return Participant(id=uuid.uuid4(), kind=ParticipantKind.USER, display_name=name)


def _bot_participant() -> Participant:
    return Participant(
        id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        kind=ParticipantKind.AGENT,
        display_name="Concierge AI",
    )


def test_generate_bot_reply_happy_path() -> None:
    conversation_repo = InMemoryConversationRepository()
    message_repo = InMemoryMessageRepository()
    user = _user_participant()
    bot = _bot_participant()
    responder = FakeChatbotResponder("こんにちは！")

    conversation = CreateConversationUseCase(conversation_repo).execute("general", user)
    PostMessageUseCase(conversation_repo, message_repo).execute(conversation.id, user, "hello")

    use_case = GenerateBotReplyUseCase(conversation_repo, message_repo, responder, bot, history_limit=20)
    bot_message = use_case.execute(conversation.id)

    assert bot_message.role == MessageRole.AGENT
    assert bot_message.content == "こんにちは！"
    assert bot_message.sender.id == bot.id
    assert bot_message.conversation_id == conversation.id

    # Verify the bot was added as participant
    updated_conversation = conversation_repo.find_by_id(conversation.id)
    assert updated_conversation is not None
    assert any(p.id == bot.id for p in updated_conversation.participants)


def test_generate_bot_reply_conversation_not_found() -> None:
    conversation_repo = InMemoryConversationRepository()
    message_repo = InMemoryMessageRepository()
    responder = FakeChatbotResponder()

    use_case = GenerateBotReplyUseCase(conversation_repo, message_repo, responder, _bot_participant())

    with pytest.raises(ConversationNotFoundError):
        use_case.execute(uuid.uuid4())


def test_generate_bot_reply_history_limit() -> None:
    conversation_repo = InMemoryConversationRepository()
    message_repo = InMemoryMessageRepository()
    user = _user_participant()
    bot = _bot_participant()
    responder = FakeChatbotResponder("reply")

    conversation = CreateConversationUseCase(conversation_repo).execute("general", user)
    for i in range(5):
        PostMessageUseCase(conversation_repo, message_repo).execute(conversation.id, user, f"message {i}")

    use_case = GenerateBotReplyUseCase(conversation_repo, message_repo, responder, bot, history_limit=2)
    use_case.execute(conversation.id)

    # The responder should only receive at most history_limit messages
    assert len(responder.received_history) <= 2
