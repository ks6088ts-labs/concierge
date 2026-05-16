from __future__ import annotations

from concierge.chat.application.responders import ChatbotResponder, RealtimeVoiceResponder
from concierge.chat.infrastructure.ai.exceptions import ChatbotNotConfiguredError
from concierge.chat.infrastructure.ai.foundry_realtime import FoundryRealtimeResponder
from concierge.chat.infrastructure.ai.foundry_responder import FoundryChatbotResponder
from concierge.settings import get_chat_settings, get_microsoft_foundry_settings

# Re-export so that existing importers from `factory` continue to work.
__all__ = ["ChatbotNotConfiguredError", "create_chatbot_responder", "create_realtime_responder"]


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


def create_realtime_responder() -> RealtimeVoiceResponder:
    """Build the realtime voice responder.

    Raises :class:`ChatbotNotConfiguredError` when
    ``AZURE_AI_PROJECT_ENDPOINT_REALTIME`` is not set or empty.
    """
    foundry_settings = get_microsoft_foundry_settings()
    if not foundry_settings.azure_ai_project_endpoint_realtime:
        raise ChatbotNotConfiguredError(
            "AZURE_AI_PROJECT_ENDPOINT_REALTIME is not configured; cannot build the realtime responder.",
        )
    settings = get_chat_settings()
    return FoundryRealtimeResponder(
        endpoint_realtime=foundry_settings.azure_ai_project_endpoint_realtime,
        deployment=settings.realtime_model,
        voice=settings.realtime_voice,
        locale=settings.realtime_locale,
        system_prompt=settings.realtime_system_prompt,
    )
