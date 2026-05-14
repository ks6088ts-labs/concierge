from __future__ import annotations

import copy
import uuid
from datetime import datetime

from concierge.chat.domain.entities import Conversation, Message


class InMemoryConversationRepository:
    def __init__(self):
        self._conversations: dict[uuid.UUID, Conversation] = {}

    def save(self, conversation: Conversation) -> Conversation:
        self._conversations[conversation.id] = copy.deepcopy(conversation)
        return copy.deepcopy(self._conversations[conversation.id])

    def find_by_id(self, conversation_id: uuid.UUID) -> Conversation | None:
        conversation = self._conversations.get(conversation_id)
        return copy.deepcopy(conversation) if conversation is not None else None

    def find_all(self, *, participant_id: uuid.UUID | None = None) -> list[Conversation]:
        conversations = self._conversations.values()
        if participant_id is not None:
            conversations = [
                conversation
                for conversation in conversations
                if any(participant.id == participant_id for participant in conversation.participants)
            ]
        return [copy.deepcopy(conversation) for conversation in conversations]

    def delete(self, conversation_id: uuid.UUID) -> bool:
        return self._conversations.pop(conversation_id, None) is not None


class InMemoryMessageRepository:
    def __init__(self):
        self._messages: dict[uuid.UUID, list[Message]] = {}

    def save(self, message: Message) -> Message:
        bucket = self._messages.setdefault(message.conversation_id, [])
        for index, existing in enumerate(bucket):
            if existing.id == message.id:
                bucket[index] = copy.deepcopy(message)
                return copy.deepcopy(bucket[index])
        bucket.append(copy.deepcopy(message))
        return copy.deepcopy(bucket[-1])

    def find_by_conversation(
        self,
        conversation_id: uuid.UUID,
        *,
        limit: int = 100,
        before: datetime | None = None,
    ) -> list[Message]:
        messages = self._messages.get(conversation_id, [])
        filtered = messages
        if before is not None:
            filtered = [message for message in filtered if message.created_at < before]
        ordered = sorted(filtered, key=lambda message: message.created_at, reverse=True)
        return [copy.deepcopy(message) for message in ordered[:limit]]

    def delete_by_conversation(self, conversation_id: uuid.UUID) -> int:
        messages = self._messages.pop(conversation_id, [])
        return len(messages)
