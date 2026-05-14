from __future__ import annotations

from concierge.chat.domain.entities import Conversation, Message


class ChatbotDisabledError(Exception):
    """Raised when the chatbot responder is disabled or not configured."""


class NullChatbotResponder:
    def generate_reply(self, conversation: Conversation, history: list[Message]) -> str:
        raise ChatbotDisabledError("Chatbot is disabled")
