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
