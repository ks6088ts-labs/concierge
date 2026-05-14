from __future__ import annotations

import uuid

import pytest

from concierge.chat.application.use_cases import (
    CreateConversationUseCase,
    DeleteConversationUseCase,
    GetConversationUseCase,
    JoinConversationUseCase,
    ListConversationsUseCase,
    ListMessagesUseCase,
    PostMessageUseCase,
)
from concierge.chat.domain.exceptions import ConversationNotFoundError, MessageValidationError
from concierge.chat.domain.value_objects import Participant, ParticipantKind
from concierge.chat.infrastructure.persistence.memory import InMemoryConversationRepository, InMemoryMessageRepository


def _participant(name: str = "alice") -> Participant:
    return Participant(id=uuid.uuid4(), kind=ParticipantKind.USER, display_name=name)


def test_use_cases_happy_path() -> None:
    conversation_repo = InMemoryConversationRepository()
    message_repo = InMemoryMessageRepository()
    participant = _participant()

    conversation = CreateConversationUseCase(conversation_repo).execute("general", participant)
    JoinConversationUseCase(conversation_repo).execute(conversation.id, participant)
    message = PostMessageUseCase(conversation_repo, message_repo).execute(conversation.id, participant, "hello")

    fetched = GetConversationUseCase(conversation_repo).execute(conversation.id)
    listed = ListConversationsUseCase(conversation_repo).execute(participant_id=participant.id)
    messages = ListMessagesUseCase(conversation_repo, message_repo).execute(conversation.id)

    assert fetched.id == conversation.id
    assert len(listed) == 1
    assert messages[0].id == message.id

    DeleteConversationUseCase(conversation_repo, message_repo).execute(conversation.id)
    assert conversation_repo.find_by_id(conversation.id) is None


def test_missing_conversation_raises() -> None:
    conversation_repo = InMemoryConversationRepository()
    message_repo = InMemoryMessageRepository()

    with pytest.raises(ConversationNotFoundError):
        GetConversationUseCase(conversation_repo).execute(uuid.uuid4())

    with pytest.raises(ConversationNotFoundError):
        ListMessagesUseCase(conversation_repo, message_repo).execute(uuid.uuid4())


def test_non_participant_cannot_post_message() -> None:
    conversation_repo = InMemoryConversationRepository()
    message_repo = InMemoryMessageRepository()

    owner = _participant("owner")
    conversation = CreateConversationUseCase(conversation_repo).execute("general", owner)

    with pytest.raises(MessageValidationError):
        PostMessageUseCase(conversation_repo, message_repo).execute(conversation.id, _participant("other"), "hello")
