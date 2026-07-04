from __future__ import annotations

import os
import warnings

from concierge.chat.application.realtime_tools import RealtimeTool
from concierge.chat.application.responders import ChatbotResponder, RealtimeVoiceResponder
from concierge.chat.infrastructure.ai.exceptions import ChatbotNotConfiguredError
from concierge.chat.infrastructure.ai.foundry_realtime import FoundryRealtimeResponder
from concierge.chat.infrastructure.ai.foundry_responder import FoundryChatbotResponder
from concierge.chat.infrastructure.ai.realtime_tools import build_default_realtime_tools
from concierge.settings import get_chat_settings, get_microsoft_foundry_settings
from concierge.settings.chat import FOUNDRY_BOT_AGENT_TYPE

# Re-export so that existing importers from `factory` continue to work.
__all__ = [
    "ChatbotNotConfiguredError",
    "create_chatbot_responder",
    "create_realtime_responder",
    "create_realtime_responder_with_tools",
    "list_available_agent_types",
]


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
            "'echo', 'langgraph', 'github-copilot-sdk', 'microsoft-agent-framework').",
            DeprecationWarning,
            stacklevel=3,
        )
        _legacy_warning_emitted = True


def create_chatbot_responder(agent_type: str | None = None) -> ChatbotResponder:
    """Build the chatbot responder.

    Selection rules:

    * ``foundry`` — streaming :class:`FoundryChatbotResponder`. Requires
      ``AZURE_AI_PROJECT_ENDPOINT``.
    * Any other value — resolved from the shared :class:`AgentRegistry` and
      wrapped in :class:`AgentChatbotResponder`. Built-in values: ``echo``,
      ``langgraph``, ``github-copilot-sdk``, ``microsoft-agent-framework``.

    When ``agent_type`` is ``None`` (or an empty string) the value of
    ``CHAT_BOT_AGENT_TYPE`` (``ChatSettings.bot_agent_type``) is used. Passing
    an explicit ``agent_type`` lets callers (e.g. the web UI) override the
    default on a per-request basis.

    Raises :class:`ChatbotNotConfiguredError` when the backend is not properly
    configured (missing Foundry endpoint, or unknown agent type).
    """
    _warn_if_legacy_responder_backend_set()

    chat_settings = get_chat_settings()
    bot_agent_type = agent_type or chat_settings.bot_agent_type

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
            f"agent_type={bot_agent_type!r} is not a known responder. Valid values: {valid_types}.",
        ) from exc
    return AgentChatbotResponder(agent)


def list_available_agent_types() -> list[str]:
    """Return all agent types selectable by the web UI.

    The list always includes the entries from the shared :class:`AgentRegistry`
    (e.g. ``echo``, ``langgraph``, ``github-copilot-sdk``,
    ``microsoft-agent-framework``). The Foundry
    streaming responder is only included when ``AZURE_AI_PROJECT_ENDPOINT`` is
    configured, because attempting to use it would otherwise fail at request
    time with a 503.
    """
    from concierge.agents.infrastructure.registry_factory import get_agent_registry

    types: list[str] = []
    foundry_settings = get_microsoft_foundry_settings()
    if foundry_settings.azure_ai_project_endpoint:
        types.append(FOUNDRY_BOT_AGENT_TYPE)
    types.extend(get_agent_registry().list_agent_types())
    return types


def create_realtime_responder(
    system_prompt: str | None = None,
    extra_tools: list[RealtimeTool] | None = None,
) -> RealtimeVoiceResponder:
    """Build the realtime voice responder.

    Args:
        system_prompt: When provided, overrides ``CHAT_REALTIME_SYSTEM_PROMPT``
            for this session (used by the accessibility mode to inject its
            slow / simple-concept instructions).
        extra_tools: Additional :class:`RealtimeTool` instances advertised to
            the model on top of :func:`build_default_realtime_tools` (used by
            the accessibility mode to expose ``capture_image``).

    Raises :class:`ChatbotNotConfiguredError` when
    ``AZURE_AI_PROJECT_ENDPOINT_REALTIME`` is not set or empty.
    """
    responder, _ = create_realtime_responder_with_tools(
        system_prompt=system_prompt,
        extra_tools=extra_tools,
    )
    return responder


def create_realtime_responder_with_tools(
    system_prompt: str | None = None,
    extra_tools: list[RealtimeTool] | None = None,
) -> tuple[RealtimeVoiceResponder, list[RealtimeTool]]:
    """Build the realtime responder and return the exact advertised tools.

    WebSocket routes need both objects: the responder advertises tool schemas in
    ``session.update`` and :class:`StreamRealtimeVoiceUseCase` executes the same
    tool handlers. Returning both from one function avoids duplicate tool
    construction and keeps the two sides in lock-step.
    """
    foundry_settings = get_microsoft_foundry_settings()
    if not foundry_settings.azure_ai_project_endpoint_realtime:
        raise ChatbotNotConfiguredError(
            "AZURE_AI_PROJECT_ENDPOINT_REALTIME is not configured; cannot build the realtime responder.",
        )
    settings = get_chat_settings()
    tools = [*build_default_realtime_tools(), *(extra_tools or [])]
    responder = FoundryRealtimeResponder(
        endpoint_realtime=foundry_settings.azure_ai_project_endpoint_realtime,
        deployment=settings.realtime_model,
        voice=settings.realtime_voice,
        locale=settings.realtime_locale,
        system_prompt=system_prompt if system_prompt is not None else settings.realtime_system_prompt,
        transcription_model=settings.realtime_transcription_model,
        tools=tools,
        turn_detection_type=settings.realtime_turn_detection_type,
        vad_threshold=settings.realtime_vad_threshold,
        vad_prefix_padding_ms=settings.realtime_vad_prefix_padding_ms,
        vad_silence_duration_ms=settings.realtime_vad_silence_duration_ms,
        vad_eagerness=settings.realtime_vad_eagerness,
        vad_create_response=settings.realtime_vad_create_response,
        vad_interrupt_response=settings.realtime_vad_interrupt_response,
    )
    return responder, tools
