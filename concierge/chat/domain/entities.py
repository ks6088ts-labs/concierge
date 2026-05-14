from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from concierge.chat.domain.exceptions import MessageValidationError
from concierge.chat.domain.value_objects import MessageRole, Participant


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Conversation:
    title: str
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    participants: list[Participant] = field(default_factory=list)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        self._validate_title(self.title)

    def add_participant(self, participant: Participant) -> None:
        for index, existing in enumerate(self.participants):
            if existing.id == participant.id:
                self.participants[index] = participant
                self.touch()
                return
        self.participants.append(participant)
        self.touch()

    def rename(self, title: str) -> None:
        self._validate_title(title)
        self.title = title
        self.touch()

    def touch(self) -> None:
        self.updated_at = _utcnow()

    @staticmethod
    def _validate_title(title: str) -> None:
        if not title.strip() or len(title) > 200:
            raise MessageValidationError("title must be between 1 and 200 characters")


@dataclass
class Message:
    conversation_id: uuid.UUID
    sender: Participant
    content: str
    role: MessageRole = MessageRole.USER
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        if not self.content.strip() or len(self.content) > 4000:
            raise MessageValidationError("content must be between 1 and 4000 characters")
