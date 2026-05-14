from __future__ import annotations

from datetime import timezone

import pytest

from concierge.chat.domain.entities import Conversation, Message
from concierge.chat.domain.exceptions import MessageValidationError, ParticipantValidationError
from concierge.chat.domain.value_objects import Participant, ParticipantKind


def _participant(name: str = "alice") -> Participant:
    return Participant(id=__import__("uuid").uuid4(), kind=ParticipantKind.USER, display_name=name)


def test_conversation_defaults() -> None:
    conversation = Conversation(title="general")
    assert conversation.created_at.tzinfo == timezone.utc
    assert conversation.updated_at.tzinfo == timezone.utc


def test_conversation_validates_title() -> None:
    with pytest.raises(MessageValidationError):
        Conversation(title="")


def test_message_validates_content() -> None:
    with pytest.raises(MessageValidationError):
        Message(conversation_id=__import__("uuid").uuid4(), sender=_participant(), content="")


def test_participant_validates_display_name() -> None:
    with pytest.raises(ParticipantValidationError):
        Participant(id=__import__("uuid").uuid4(), kind=ParticipantKind.USER, display_name="")


def test_add_participant_is_idempotent_and_touches_updated_at() -> None:
    participant = _participant("alice")
    conversation = Conversation(title="general", participants=[participant])
    before = conversation.updated_at
    conversation.add_participant(Participant(id=participant.id, kind=ParticipantKind.USER, display_name="alice-2"))

    assert len(conversation.participants) == 1
    assert conversation.participants[0].display_name == "alice-2"
    assert conversation.updated_at >= before


def test_rename_touches_updated_at() -> None:
    conversation = Conversation(title="general")
    before = conversation.updated_at
    conversation.rename("general-2")

    assert conversation.title == "general-2"
    assert conversation.updated_at >= before
