from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol

from concierge.chat.domain.entities import Conversation, Message


class ConversationRepository(Protocol):
    def save(self, conversation: Conversation) -> Conversation: ...

    def find_by_id(self, conversation_id: uuid.UUID) -> Conversation | None: ...

    def find_all(self, *, participant_id: uuid.UUID | None = None) -> list[Conversation]: ...

    def delete(self, conversation_id: uuid.UUID) -> bool: ...


class MessageRepository(Protocol):
    def save(self, message: Message) -> Message: ...

    def find_by_conversation(
        self,
        conversation_id: uuid.UUID,
        *,
        limit: int = 100,
        before: datetime | None = None,
    ) -> list[Message]: ...

    def delete_by_conversation(self, conversation_id: uuid.UUID) -> int: ...
