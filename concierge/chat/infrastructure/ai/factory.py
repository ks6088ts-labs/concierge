from __future__ import annotations

from concierge.chat.application.responders import ChatbotResponder
from concierge.chat.infrastructure.ai.foundry_responder import FoundryChatbotResponder
from concierge.settings import get_chat_settings, get_microsoft_foundry_settings


class ChatbotNotConfiguredError(RuntimeError):
    """Raised at startup when the chatbot dependencies are missing."""


def create_chatbot_responder() -> ChatbotResponder:
    """Build the chatbot responder.

    Raises :class:`ChatbotNotConfiguredError` when ``AZURE_AI_PROJECT_ENDPOINT``
    is not set, since the responder is unusable without a Foundry endpoint.
    """
    foundry_settings = get_microsoft_foundry_settings()
    if not foundry_settings.azure_ai_project_endpoint:
        raise ChatbotNotConfiguredError(
            "AZURE_AI_PROJECT_ENDPOINT is not configured; cannot build the chatbot responder.",
        )
    settings = get_chat_settings()
    return FoundryChatbotResponder(
        model=settings.bot_model,
        system_prompt=settings.bot_system_prompt,
    )
