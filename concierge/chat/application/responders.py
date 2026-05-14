from __future__ import annotations

from typing import Protocol

from concierge.chat.domain.entities import Conversation, Message


class ChatbotResponder(Protocol):
    def generate_reply(self, conversation: Conversation, history: list[Message]) -> str: ...
