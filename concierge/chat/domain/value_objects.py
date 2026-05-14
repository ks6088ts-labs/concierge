from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass

from concierge.chat.domain.exceptions import ParticipantValidationError


class ParticipantKind(str, enum.Enum):
    USER = "USER"
    AGENT = "AGENT"


class MessageRole(str, enum.Enum):
    USER = "USER"
    AGENT = "AGENT"
    SYSTEM = "SYSTEM"


@dataclass(frozen=True)
class Participant:
    id: uuid.UUID
    kind: ParticipantKind
    display_name: str

    def __post_init__(self) -> None:
        if not self.display_name.strip() or len(self.display_name) > 100:
            raise ParticipantValidationError("display_name must be between 1 and 100 characters")
