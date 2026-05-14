from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from concierge.chat.application.repositories import ConversationRepository, MessageRepository
from concierge.chat.application.use_cases import (
    CreateConversationUseCase,
    DeleteConversationUseCase,
    GetConversationUseCase,
    JoinConversationUseCase,
    ListConversationsUseCase,
    ListMessagesUseCase,
    PostMessageUseCase,
)
from concierge.chat.domain.value_objects import Participant
from concierge.chat.infrastructure.web.dependencies import (
    get_conversation_repository,
    get_current_participant,
    get_message_repository,
)
from concierge.chat.infrastructure.web.schemas import (
    ConversationResponse,
    CreateConversationRequest,
    JoinConversationRequest,
    MessageResponse,
    PostMessageRequest,
)

router = APIRouter(tags=["chat"])


def _with_display_name(participant: Participant, display_name: str | None) -> Participant:
    if display_name is None:
        return participant
    return Participant(id=participant.id, kind=participant.kind, display_name=display_name)


@router.post("/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: CreateConversationRequest,
    current_participant: Annotated[Participant, Depends(get_current_participant)],
    conversation_repository: Annotated[ConversationRepository, Depends(get_conversation_repository)],
) -> ConversationResponse:
    conversation = CreateConversationUseCase(conversation_repository).execute(
        title=payload.title,
        creator=_with_display_name(current_participant, payload.display_name),
    )
    return ConversationResponse.model_validate(conversation)


@router.get("/conversations", response_model=list[ConversationResponse])
def list_conversations(
    current_participant: Annotated[Participant, Depends(get_current_participant)],
    conversation_repository: Annotated[ConversationRepository, Depends(get_conversation_repository)],
    mine: bool = False,
) -> list[ConversationResponse]:
    participant_id = current_participant.id if mine else None
    conversations = ListConversationsUseCase(conversation_repository).execute(participant_id=participant_id)
    return [ConversationResponse.model_validate(conversation) for conversation in conversations]


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: uuid.UUID,
    conversation_repository: Annotated[ConversationRepository, Depends(get_conversation_repository)],
) -> ConversationResponse:
    conversation = GetConversationUseCase(conversation_repository).execute(conversation_id)
    return ConversationResponse.model_validate(conversation)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: uuid.UUID,
    conversation_repository: Annotated[ConversationRepository, Depends(get_conversation_repository)],
    message_repository: Annotated[MessageRepository, Depends(get_message_repository)],
) -> Response:
    DeleteConversationUseCase(conversation_repository, message_repository).execute(conversation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/conversations/{conversation_id}/participants", response_model=ConversationResponse)
def join_conversation(
    conversation_id: uuid.UUID,
    payload: JoinConversationRequest,
    current_participant: Annotated[Participant, Depends(get_current_participant)],
    conversation_repository: Annotated[ConversationRepository, Depends(get_conversation_repository)],
) -> ConversationResponse:
    conversation = JoinConversationUseCase(conversation_repository).execute(
        conversation_id,
        participant=_with_display_name(current_participant, payload.display_name),
    )
    return ConversationResponse.model_validate(conversation)


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_message(
    conversation_id: uuid.UUID,
    payload: PostMessageRequest,
    current_participant: Annotated[Participant, Depends(get_current_participant)],
    conversation_repository: Annotated[ConversationRepository, Depends(get_conversation_repository)],
    message_repository: Annotated[MessageRepository, Depends(get_message_repository)],
) -> MessageResponse:
    message = PostMessageUseCase(conversation_repository, message_repository).execute(
        conversation_id,
        sender=_with_display_name(current_participant, payload.display_name),
        content=payload.content,
    )
    return MessageResponse.model_validate(message)


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
def list_messages(
    conversation_id: uuid.UUID,
    conversation_repository: Annotated[ConversationRepository, Depends(get_conversation_repository)],
    message_repository: Annotated[MessageRepository, Depends(get_message_repository)],
    limit: int = 100,
    before: datetime | None = None,
) -> list[MessageResponse]:
    messages = ListMessagesUseCase(conversation_repository, message_repository).execute(
        conversation_id,
        limit=limit,
        before=before,
    )
    return [MessageResponse.model_validate(message) for message in messages]
