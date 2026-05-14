from __future__ import annotations

from concierge.chat.application.responders import ChatbotResponder
from concierge.chat.infrastructure.ai.foundry_responder import FoundryChatbotResponder
from concierge.chat.infrastructure.ai.null_responder import NullChatbotResponder
from concierge.settings import get_chat_settings, get_microsoft_foundry_settings


def create_chatbot_responder() -> ChatbotResponder:
    settings = get_chat_settings()
    foundry_settings = get_microsoft_foundry_settings()
    if settings.bot_enabled and foundry_settings.azure_ai_project_endpoint:
        return FoundryChatbotResponder(
            model=settings.bot_model,
            system_prompt=settings.bot_system_prompt,
        )
    return NullChatbotResponder()
