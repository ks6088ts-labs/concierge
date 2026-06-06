from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Response, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse

from concierge.chat.application.repositories import ConversationRepository, MessageRepository
from concierge.chat.application.responders import ChatbotResponder, RealtimeVoiceResponder
from concierge.chat.application.use_cases import (
    BotReplyComplete,
    BotReplyDelta,
    CreateConversationUseCase,
    DeleteConversationUseCase,
    GenerateBotReplyUseCase,
    GetConversationUseCase,
    JoinConversationUseCase,
    ListConversationsUseCase,
    ListMessagesUseCase,
    PostMessageUseCase,
    RealtimeError,
    RealtimeMessagePersisted,
    RealtimeServerEvent,
    StreamRealtimeVoiceUseCase,
)
from concierge.chat.domain.exceptions import ConversationNotFoundError
from concierge.chat.domain.value_objects import Participant, ParticipantKind
from concierge.chat.infrastructure.ai.factory import list_available_agent_types
from concierge.chat.infrastructure.ai.realtime_tools import build_default_realtime_tools
from concierge.chat.infrastructure.web.dependencies import (
    get_chatbot_responder,
    get_conversation_repository,
    get_current_participant,
    get_message_repository,
    get_realtime_responder_optional,
)
from concierge.chat.infrastructure.web.schemas import (
    AgentTypesResponse,
    ConversationResponse,
    CreateConversationRequest,
    JoinConversationRequest,
    MessageResponse,
    PostMessageRequest,
)
from concierge.settings import get_chat_settings
from concierge.settings.chat import ChatSettings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


def _with_display_name(participant: Participant, display_name: str | None) -> Participant:
    if display_name is None:
        return participant
    return Participant(id=participant.id, kind=participant.kind, display_name=display_name)


def _bot_participant(settings: ChatSettings) -> Participant:
    return Participant(
        id=settings.bot_participant_id,
        kind=ParticipantKind.AGENT,
        display_name=settings.bot_display_name,
    )


def get_chat_settings_dep() -> ChatSettings:
    return get_chat_settings()


@router.get("/agents", response_model=AgentTypesResponse, tags=["chat"])
def list_agents(
    chat_settings: Annotated[ChatSettings, Depends(get_chat_settings_dep)],
) -> AgentTypesResponse:
    """List agent types selectable from the chat web UI.

    Returns the server-configured default (``CHAT_BOT_AGENT_TYPE``) along with
    every type the user can pick (registered agents plus ``foundry`` when
    ``AZURE_AI_PROJECT_ENDPOINT`` is configured). The configured default is
    always present in ``available`` so the UI can still display it.
    """
    available = list_available_agent_types()
    if chat_settings.bot_agent_type not in available:
        available = [chat_settings.bot_agent_type, *available]
    return AgentTypesResponse(default=chat_settings.bot_agent_type, available=available)


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
    """Persist a user message.

    This endpoint only stores the caller's message. AI agent replies are
    delivered separately via ``POST /conversations/{id}/agent-replies``.
    """
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


def _format_sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post(
    "/conversations/{conversation_id}/agent-replies",
    responses={
        200: {
            "content": {"text/event-stream": {}},
            "description": "Server-Sent Events stream of the agent reply.",
        },
    },
)
def stream_agent_reply(
    conversation_id: uuid.UUID,
    conversation_repository: Annotated[ConversationRepository, Depends(get_conversation_repository)],
    message_repository: Annotated[MessageRepository, Depends(get_message_repository)],
    chatbot_responder: Annotated[ChatbotResponder, Depends(get_chatbot_responder)],
    chat_settings: Annotated[ChatSettings, Depends(get_chat_settings_dep)],
) -> StreamingResponse:
    """Stream an AI agent reply over Server-Sent Events.

    Query parameters:

    - ``agent_type`` (optional) — override the server-configured
      ``CHAT_BOT_AGENT_TYPE`` for this request only. Must be one of the values
      returned by ``GET /agents``. When omitted, the configured default is
      used.

    Connection protocol:

    - ``event: delta`` ``data: {"content": "<chunk>"}`` — emitted for each
      partial token as the model produces it.
    - ``event: complete`` ``data: <MessageResponse JSON>`` — emitted once at
      the end with the persisted ``MessageResponse``.

    Synchronous validation (e.g. unknown ``conversation_id``) is reported via
    a normal JSON error response (404 / 422 / 503) before the stream starts.
    """
    use_case = GenerateBotReplyUseCase(
        conversation_repository,
        message_repository,
        chatbot_responder,
        _bot_participant(chat_settings),
        chat_settings.bot_history_limit,
    )
    events = use_case.execute(conversation_id)

    def event_stream():
        try:
            for event in events:
                if isinstance(event, BotReplyDelta):
                    yield _format_sse("delta", {"content": event.content})
                elif isinstance(event, BotReplyComplete):
                    payload = MessageResponse.model_validate(event.message).model_dump(mode="json")
                    yield _format_sse("complete", payload)
        except Exception as exc:  # noqa: BLE001 — surface as SSE error event
            logger.exception("Bot reply stream failed for conversation %s", conversation_id)
            yield _format_sse("error", {"detail": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# WebSocket: Realtime voice relay
# ---------------------------------------------------------------------------

# Custom WS close codes
_WS_CLOSE_BAD_REQUEST = 4400
_WS_CLOSE_NOT_FOUND = 4404
_WS_CLOSE_SERVICE_UNAVAILABLE = 4503


@router.websocket("/conversations/{conversation_id}/realtime")
async def realtime_voice(
    websocket: WebSocket,
    conversation_id: uuid.UUID,
    user_id: str,
    display_name: str | None = None,
    realtime_responder: RealtimeVoiceResponder | None = Depends(get_realtime_responder_optional),
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
    message_repo: MessageRepository = Depends(get_message_repository),
) -> None:
    """WebSocket endpoint that proxies audio events between the browser and Foundry.

    Query parameters:
    - ``user_id`` (required): UUID of the calling user.
    - ``display_name`` (optional): display name for the participant.

    Close codes:
    - ``4400`` — ``user_id`` is missing or not a valid UUID.
    - ``4404`` — ``conversation_id`` does not exist.
    - ``4503`` — ``AZURE_AI_PROJECT_ENDPOINT_REALTIME`` is not configured.
    """
    import asyncio
    import threading

    # --- validate realtime responder availability ---
    if realtime_responder is None:
        await websocket.close(
            code=_WS_CLOSE_SERVICE_UNAVAILABLE,
            reason="AZURE_AI_PROJECT_ENDPOINT_REALTIME is not configured",
        )
        return

    # --- validate user_id before accepting ---
    try:
        parsed_user_id = uuid.UUID(user_id)
    except (ValueError, AttributeError):
        await websocket.close(code=_WS_CLOSE_BAD_REQUEST, reason="user_id must be a valid UUID")
        return

    # --- resolve participant ---
    resolved_display_name = display_name or f"user-{str(parsed_user_id)[:8]}"
    current_participant = Participant(id=parsed_user_id, kind=ParticipantKind.USER, display_name=resolved_display_name)

    # --- validate conversation existence before accepting ---
    chat_settings = get_chat_settings()
    bot_participant = _bot_participant(chat_settings)

    if conversation_repo.find_by_id(conversation_id) is None:
        await websocket.close(code=_WS_CLOSE_NOT_FOUND, reason=f"Conversation {conversation_id} not found")
        return

    # --- accept the connection ---
    await websocket.accept()
    await websocket.send_json({"type": "concierge.session.ready", "conversation_id": str(conversation_id)})

    use_case = StreamRealtimeVoiceUseCase(
        conversation_repository=conversation_repo,
        message_repository=message_repo,
        responder=realtime_responder,
        bot_participant=bot_participant,
        current_participant=current_participant,
        history_limit=chat_settings.bot_history_limit,
        tools=build_default_realtime_tools(),
    )

    try:
        events = use_case.execute(conversation_id)
    except ConversationNotFoundError:
        await websocket.send_json({"type": "concierge.error", "detail": f"Conversation {conversation_id} not found"})
        await websocket.close()
        return

    loop = asyncio.get_running_loop()

    # Server→Client relay runs in a background thread (session.iter_server_events is sync)
    def _run_relay() -> None:
        try:
            for event in events:
                if isinstance(event, RealtimeServerEvent):
                    asyncio.run_coroutine_threadsafe(
                        websocket.send_json({"type": "oai-event", "payload": event.payload}),
                        loop,
                    )
                elif isinstance(event, RealtimeMessagePersisted):
                    payload = MessageResponse.model_validate(event.message).model_dump(mode="json")
                    asyncio.run_coroutine_threadsafe(
                        websocket.send_json({"type": "concierge.message.persisted", "message": payload}),
                        loop,
                    )
                elif isinstance(event, RealtimeError):
                    asyncio.run_coroutine_threadsafe(
                        websocket.send_json({"type": "concierge.error", "detail": event.detail}),
                        loop,
                    )
        except Exception:  # noqa: BLE001
            pass

    relay_thread = threading.Thread(target=_run_relay, daemon=True)
    relay_thread.start()

    # Client→Server: receive from browser and forward to the upstream session
    try:
        while True:
            try:
                data = await websocket.receive_json()
                if isinstance(data, dict) and data.get("type") == "oai-event":
                    payload = data.get("payload")
                    if isinstance(payload, dict):
                        use_case.send_client_event(payload)
            except WebSocketDisconnect:
                break
    except Exception:  # noqa: BLE001
        pass
    finally:
        relay_thread.join(timeout=2)
