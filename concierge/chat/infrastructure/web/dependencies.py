from __future__ import annotations

import uuid

from fastapi import Header, HTTPException, Query, status

from concierge.chat.application.realtime_tools import RealtimeTool, build_capture_image_tool
from concierge.chat.application.repositories import ConversationRepository, MessageRepository
from concierge.chat.application.responders import ChatbotResponder, RealtimeVoiceResponder
from concierge.chat.domain.exceptions import ParticipantValidationError
from concierge.chat.domain.value_objects import Participant, ParticipantKind
from concierge.chat.infrastructure.ai.factory import (
    ChatbotNotConfiguredError,
    create_chatbot_responder,
    create_realtime_responder,
    create_realtime_responder_with_tools,
)
from concierge.chat.infrastructure.persistence.factory import (
    get_conversation_repository as _factory_get_conversation_repository,
)
from concierge.chat.infrastructure.persistence.factory import get_message_repository as _factory_get_message_repository
from concierge.settings import get_chat_settings

RealtimeResponderBundle = tuple[RealtimeVoiceResponder, list[RealtimeTool]]


def get_conversation_repository() -> ConversationRepository:
    return _factory_get_conversation_repository()


def get_message_repository() -> MessageRepository:
    return _factory_get_message_repository()


def get_chatbot_responder(
    agent_type: str | None = Query(default=None, alias="agent_type"),
) -> ChatbotResponder:
    """Build the chatbot responder for the current request.

    Accepts an optional ``?agent_type=`` query parameter that overrides the
    ``CHAT_BOT_AGENT_TYPE`` setting. When not provided, the configured default
    is used.
    """
    try:
        return create_chatbot_responder(agent_type=agent_type)
    except ChatbotNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


def get_realtime_responder() -> RealtimeVoiceResponder:
    try:
        return create_realtime_responder()
    except ChatbotNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


def get_realtime_responder_optional() -> RealtimeVoiceResponder | None:
    """Like :func:`get_realtime_responder` but returns ``None`` on misconfiguration.

    Used by WebSocket handlers that must close with a custom close code (4503)
    rather than an HTTP 503 response.
    """
    try:
        return create_realtime_responder()
    except ChatbotNotConfiguredError:
        return None


def get_realtime_responder_bundle_optional(
    mode: str | None = Query(default=None, alias="mode"),
) -> RealtimeResponderBundle | None:
    """Build the realtime responder plus the exact tools it advertised.

    ``mode=accessible`` selects the deafblind accessibility prompt and adds the
    hands-free ``capture_image`` tool. Returning the responder and tool list as
    one bundle keeps ``session.tools`` and the use-case handler registry
    synchronized without constructing the default tool set twice.
    """
    try:
        if mode == "accessible":
            settings = get_chat_settings()
            return create_realtime_responder_with_tools(
                system_prompt=settings.realtime_accessible_system_prompt,
                extra_tools=[build_capture_image_tool()],
            )
        return create_realtime_responder_with_tools()
    except ChatbotNotConfiguredError:
        return None


def get_current_participant(
    x_user_id: str = Header(..., alias="X-User-Id"),
    display_name: str | None = Query(default=None, alias="display_name"),
) -> Participant:
    try:
        user_id = uuid.UUID(x_user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="X-User-Id must be a UUID",
        ) from exc

    resolved_display_name = display_name or f"user-{str(user_id)[:8]}"
    try:
        return Participant(id=user_id, kind=ParticipantKind.USER, display_name=resolved_display_name)
    except ParticipantValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
