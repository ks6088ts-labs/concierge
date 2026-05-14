from __future__ import annotations

import uuid

from fastapi import Header, HTTPException, Query, status

from concierge.chat.application.repositories import ConversationRepository, MessageRepository
from concierge.chat.domain.exceptions import ParticipantValidationError
from concierge.chat.domain.value_objects import Participant, ParticipantKind
from concierge.chat.infrastructure.persistence.factory import (
    get_conversation_repository as _factory_get_conversation_repository,
)
from concierge.chat.infrastructure.persistence.factory import get_message_repository as _factory_get_message_repository


def get_conversation_repository() -> ConversationRepository:
    return _factory_get_conversation_repository()


def get_message_repository() -> MessageRepository:
    return _factory_get_message_repository()


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
