from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from concierge.chat.domain.value_objects import MessageRole, ParticipantKind


class ParticipantResponse(BaseModel):
    id: uuid.UUID
    kind: ParticipantKind
    display_name: str

    model_config = {"from_attributes": True}


class ConversationResponse(BaseModel):
    id: uuid.UUID
    title: str
    participants: list[ParticipantResponse]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    sender: ParticipantResponse
    role: MessageRole
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CreateConversationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    display_name: str | None = Field(default=None, min_length=1, max_length=100)


class JoinConversationRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=100)


class PostMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000)
    display_name: str | None = Field(default=None, min_length=1, max_length=100)


class AgentReplyRequest(BaseModel):
    """Optional body for ``POST /conversations/{id}/agent-replies``.

    ``image_url`` carries a camera-captured image for this turn as an inline
    ``data:image/*;base64,…`` URL. It is request-scoped and never persisted
    (ephemeral). The body is optional so existing no-body callers keep working.
    """

    image_url: str | None = Field(default=None)


class AgentTypesResponse(BaseModel):
    """List of agent types selectable from the chat-web UI.

    ``default`` reflects the server-side configuration (``CHAT_BOT_AGENT_TYPE``);
    ``available`` lists every type the user can pick. The server-configured
    default is always included, even when it is not currently usable, so the UI
    can surface it (e.g. ``foundry`` without ``AZURE_AI_PROJECT_ENDPOINT``).
    """

    default: str
    available: list[str]
