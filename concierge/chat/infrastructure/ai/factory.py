from __future__ import annotations

import os
import warnings

from concierge.chat.application.responders import ChatbotResponder, RealtimeVoiceResponder
from concierge.chat.infrastructure.ai.exceptions import ChatbotNotConfiguredError
from concierge.chat.infrastructure.ai.foundry_realtime import FoundryRealtimeResponder
from concierge.chat.infrastructure.ai.foundry_responder import FoundryChatbotResponder
from concierge.settings import get_chat_settings, get_microsoft_foundry_settings
from concierge.settings.chat import FOUNDRY_BOT_AGENT_TYPE

# Re-export so that existing importers from `factory` continue to work.
__all__ = ["ChatbotNotConfiguredError", "create_chatbot_responder", "create_realtime_responder"]


_LEGACY_RESPONDER_BACKEND_ENV = "CHAT_RESPONDER_BACKEND"
_legacy_warning_emitted = False


def _warn_if_legacy_responder_backend_set() -> None:
    """Emit a one-time DeprecationWarning if the obsolete env var is set.

    ``CHAT_RESPONDER_BACKEND`` was removed in favour of treating ``foundry``
    as just another value of ``CHAT_BOT_AGENT_TYPE``. The variable is silently
    ignored by pydantic-settings (``extra="ignore"``), so without this warning
    a stale ``.env`` would produce no diagnostic at all.
    """
    global _legacy_warning_emitted
    if _legacy_warning_emitted:
        return
    if _LEGACY_RESPONDER_BACKEND_ENV in os.environ:
        warnings.warn(
            f"{_LEGACY_RESPONDER_BACKEND_ENV} is deprecated and ignored. "
            f"Use CHAT_BOT_AGENT_TYPE={FOUNDRY_BOT_AGENT_TYPE!r} for the Foundry "
            "responder, or one of the registered agent types (e.g. "
            "'echo', 'langgraph-echo', 'github-copilot-echo').",
            DeprecationWarning,
            stacklevel=3,
        )
        _legacy_warning_emitted = True


def create_chatbot_responder() -> ChatbotResponder:
    """Build the chatbot responder.

    Selection is driven by a single env var, ``CHAT_BOT_AGENT_TYPE``:

    * ``foundry`` (default) — streaming :class:`FoundryChatbotResponder`.
      Requires ``AZURE_AI_PROJECT_ENDPOINT``.
    * Any other value — resolved from the shared :class:`AgentRegistry` and
      wrapped in :class:`AgentChatbotResponder`. Built-in values: ``echo``,
      ``langgraph-echo``, ``github-copilot-echo``.

    Raises :class:`ChatbotNotConfiguredError` when the backend is not properly
    configured (missing Foundry endpoint, or unknown agent type).
    """
    _warn_if_legacy_responder_backend_set()

    chat_settings = get_chat_settings()
    bot_agent_type = chat_settings.bot_agent_type

    if bot_agent_type == FOUNDRY_BOT_AGENT_TYPE:
        foundry_settings = get_microsoft_foundry_settings()
        if not foundry_settings.azure_ai_project_endpoint:
            raise ChatbotNotConfiguredError(
                "AZURE_AI_PROJECT_ENDPOINT is not configured; cannot build the chatbot responder.",
            )
        return FoundryChatbotResponder(
            model=chat_settings.bot_model,
            system_prompt=chat_settings.bot_system_prompt,
        )

    # Agent-backed path.
    from concierge.agents.application.registry import AgentRegistry
    from concierge.agents.domain.exceptions import AgentNotFoundError
    from concierge.agents.infrastructure.registry_factory import get_agent_registry
    from concierge.chat.infrastructure.ai.agent_responder import AgentChatbotResponder

    registry: AgentRegistry = get_agent_registry()
    try:
        agent = registry.resolve(bot_agent_type)
    except AgentNotFoundError as exc:
        valid_types = [FOUNDRY_BOT_AGENT_TYPE, *registry.list_agent_types()]
        raise ChatbotNotConfiguredError(
            f"CHAT_BOT_AGENT_TYPE={bot_agent_type!r} is not a known responder. Valid values: {valid_types}.",
        ) from exc
    return AgentChatbotResponder(agent)


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
        transcription_model=settings.realtime_transcription_model,
    )
