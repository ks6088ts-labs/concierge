from __future__ import annotations

import uuid

from concierge.chat.domain.entities import Conversation, Message
from concierge.chat.domain.value_objects import Participant, ParticipantKind
from concierge.chat.infrastructure.persistence.memory import InMemoryConversationRepository, InMemoryMessageRepository


def _participant() -> Participant:
    return Participant(id=uuid.uuid4(), kind=ParticipantKind.USER, display_name="alice")


def test_memory_conversation_repository_crud_and_copy() -> None:
    repo = InMemoryConversationRepository()
    conversation = Conversation(title="general", participants=[_participant()])

    saved = repo.save(conversation)
    saved.title = "changed"

    found = repo.find_by_id(conversation.id)
    assert found is not None
    assert found.title == "general"
    assert repo.delete(conversation.id) is True


def test_memory_message_repository_crud_and_copy() -> None:
    repo = InMemoryMessageRepository()
    conversation_id = uuid.uuid4()
    message = Message(conversation_id=conversation_id, sender=_participant(), content="hello")

    saved = repo.save(message)
    saved.content = "changed"

    listed = repo.find_by_conversation(conversation_id)
    assert listed[0].content == "hello"
    assert repo.delete_by_conversation(conversation_id) == 1
