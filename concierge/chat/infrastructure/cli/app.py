from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import Annotated

import typer
from dotenv import load_dotenv

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
)
from concierge.chat.domain.entities import Conversation, Message
from concierge.chat.domain.exceptions import (
    ConversationNotFoundError,
    MessageValidationError,
    ParticipantValidationError,
)
from concierge.chat.domain.value_objects import Participant, ParticipantKind
from concierge.chat.infrastructure.ai.factory import ChatbotNotConfiguredError, create_chatbot_responder
from concierge.chat.infrastructure.persistence.factory import get_conversation_repository, get_message_repository
from concierge.chat.infrastructure.persistence.postgres import (
    SqlAlchemyConversationRepository,
    SqlAlchemyMessageRepository,
)
from concierge.settings import ChatRepositoryBackend, get_chat_settings

app = typer.Typer(add_completion=False, help="Chat CLI")
conversation_app = typer.Typer(help="Conversation commands")
message_app = typer.Typer(help="Message commands")
db_app = typer.Typer(help="Database management commands")
app.add_typer(conversation_app, name="conversation")
app.add_typer(message_app, name="message")
app.add_typer(db_app, name="db")


@app.callback()
def _bootstrap() -> None:
    """Load ``.env`` so libraries that read ``os.environ`` (e.g. ``langchain-azure-ai``) see the values.

    ``pydantic-settings`` reads ``.env`` directly for our own settings classes,
    but third-party libraries look up configuration via ``os.environ``.
    Existing process env vars take precedence (``override=False`` by default).
    """
    load_dotenv()


def _conversation_to_dict(conversation: Conversation) -> dict[str, object]:
    return {
        "id": str(conversation.id),
        "title": conversation.title,
        "participants": [
            {
                "id": str(participant.id),
                "kind": participant.kind.value,
                "display_name": participant.display_name,
            }
            for participant in conversation.participants
        ],
        "created_at": conversation.created_at.isoformat(),
        "updated_at": conversation.updated_at.isoformat(),
    }


def _message_to_dict(message: Message) -> dict[str, object]:
    return {
        "id": str(message.id),
        "conversation_id": str(message.conversation_id),
        "sender": {
            "id": str(message.sender.id),
            "kind": message.sender.kind.value,
            "display_name": message.sender.display_name,
        },
        "role": message.role.value,
        "content": message.content,
        "created_at": message.created_at.isoformat(),
    }


def _print_json(payload: object) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=False))


def _handle_error(exc: Exception) -> None:
    typer.echo(str(exc), err=True)
    raise typer.Exit(code=1) from exc


def _resolve_user_id(user_id: uuid.UUID | None) -> uuid.UUID:
    if user_id is not None:
        return user_id
    env_user_id = os.getenv("CHAT_USER_ID")
    if env_user_id:
        return uuid.UUID(env_user_id)
    return uuid.uuid4()


def _build_participant(user_id: uuid.UUID | None, display_name: str | None) -> Participant:
    resolved_user_id = _resolve_user_id(user_id)
    return Participant(
        id=resolved_user_id,
        kind=ParticipantKind.USER,
        display_name=display_name or f"user-{str(resolved_user_id)[:8]}",
    )


def _require_sql_backend() -> None:
    if get_chat_settings().repository_backend is ChatRepositoryBackend.MEMORY:
        typer.echo(
            "The 'db' commands are not applicable for the 'memory' backend. "
            "Set CHAT_REPOSITORY_BACKEND to 'postgres' or 'azure-postgres'.",
            err=True,
        )
        raise typer.Exit(code=1)


@conversation_app.command("create")
def conversation_create(
    title: Annotated[str, typer.Option("--title", help="Conversation title")],
    display_name: Annotated[str | None, typer.Option("--display-name", help="Display name")] = None,
    user_id: Annotated[uuid.UUID | None, typer.Option("--user-id", help="User ID")] = None,
) -> None:
    try:
        participant = _build_participant(user_id, display_name)
        conversation = CreateConversationUseCase(get_conversation_repository()).execute(
            title=title,
            creator=participant,
        )
        _print_json(_conversation_to_dict(conversation))
    except (MessageValidationError, ParticipantValidationError, ValueError) as exc:
        _handle_error(exc)


@conversation_app.command("list")
def conversation_list(
    mine: Annotated[bool, typer.Option("--mine", help="Show only conversations you participate in")] = False,
    user_id: Annotated[uuid.UUID | None, typer.Option("--user-id", help="User ID")] = None,
) -> None:
    participant_id = _resolve_user_id(user_id) if mine else None
    conversations = ListConversationsUseCase(get_conversation_repository()).execute(participant_id=participant_id)
    _print_json([_conversation_to_dict(conversation) for conversation in conversations])


@conversation_app.command("get")
def conversation_get(conversation_id: uuid.UUID) -> None:
    try:
        conversation = GetConversationUseCase(get_conversation_repository()).execute(conversation_id)
        _print_json(_conversation_to_dict(conversation))
    except ConversationNotFoundError as exc:
        _handle_error(exc)


@conversation_app.command("delete")
def conversation_delete(conversation_id: uuid.UUID) -> None:
    try:
        DeleteConversationUseCase(get_conversation_repository(), get_message_repository()).execute(conversation_id)
        typer.echo("deleted")
    except ConversationNotFoundError as exc:
        _handle_error(exc)


@message_app.command("post")
def message_post(
    conversation_id: uuid.UUID,
    content: Annotated[str, typer.Option("--content", help="Message content")],
    display_name: Annotated[str | None, typer.Option("--display-name", help="Display name")] = None,
    user_id: Annotated[uuid.UUID | None, typer.Option("--user-id", help="User ID")] = None,
) -> None:
    try:
        participant = _build_participant(user_id, display_name)
        JoinConversationUseCase(get_conversation_repository()).execute(conversation_id, participant)
        message = PostMessageUseCase(get_conversation_repository(), get_message_repository()).execute(
            conversation_id,
            sender=participant,
            content=content,
        )
        _print_json(_message_to_dict(message))
    except (ConversationNotFoundError, MessageValidationError, ParticipantValidationError, ValueError) as exc:
        _handle_error(exc)


@message_app.command("list")
def message_list(
    conversation_id: uuid.UUID,
    limit: Annotated[int, typer.Option("--limit", help="Maximum message count")] = 100,
    before: Annotated[str | None, typer.Option("--before", help="ISO8601 timestamp")] = None,
) -> None:
    try:
        parsed_before = datetime.fromisoformat(before) if before else None
        messages = ListMessagesUseCase(get_conversation_repository(), get_message_repository()).execute(
            conversation_id,
            limit=limit,
            before=parsed_before,
        )
        _print_json([_message_to_dict(message) for message in messages])
    except (ConversationNotFoundError, ValueError) as exc:
        _handle_error(exc)


@db_app.command("init")
def db_init() -> None:
    _require_sql_backend()
    conversation_repository = get_conversation_repository()
    message_repository = get_message_repository()
    if not isinstance(conversation_repository, SqlAlchemyConversationRepository) or not isinstance(
        message_repository, SqlAlchemyMessageRepository
    ):
        typer.echo("Backend does not support schema initialisation.", err=True)
        raise typer.Exit(code=1)
    conversation_repository.init_schema()
    message_repository.init_schema()
    typer.echo("Database schema initialised successfully.")


@db_app.command("drop")
def db_drop(
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    _require_sql_backend()
    conversation_repository = get_conversation_repository()
    message_repository = get_message_repository()
    if not isinstance(conversation_repository, SqlAlchemyConversationRepository) or not isinstance(
        message_repository, SqlAlchemyMessageRepository
    ):
        typer.echo("Backend does not support schema management.", err=True)
        raise typer.Exit(code=1)
    if not yes:
        typer.confirm("This will drop chat tables. Continue?", abort=True)
    message_repository.drop_schema()
    conversation_repository.drop_schema()
    typer.echo("Tables dropped.")


@db_app.command("ping")
def db_ping() -> None:
    _require_sql_backend()
    conversation_repository = get_conversation_repository()
    if not isinstance(conversation_repository, SqlAlchemyConversationRepository):
        typer.echo("Backend does not support ping.", err=True)
        raise typer.Exit(code=1)
    conversation_repository.ping()
    typer.echo("Connection OK.")


@message_app.command("reply")
def message_reply(conversation_id: uuid.UUID) -> None:
    """Stream an AI agent reply and print the final ``MessageResponse`` JSON."""
    settings = get_chat_settings()
    try:
        responder = create_chatbot_responder()
    except ChatbotNotConfiguredError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    bot_participant = Participant(
        id=settings.bot_participant_id,
        kind=ParticipantKind.AGENT,
        display_name=settings.bot_display_name,
    )
    try:
        events = GenerateBotReplyUseCase(
            get_conversation_repository(),
            get_message_repository(),
            responder,
            bot_participant,
            settings.bot_history_limit,
        ).execute(conversation_id)
    except ConversationNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    final_message: Message | None = None
    for event in events:
        if isinstance(event, BotReplyDelta):
            typer.echo(event.content, nl=False)
        elif isinstance(event, BotReplyComplete):
            final_message = event.message
    typer.echo()  # newline after streamed content
    if final_message is not None:
        _print_json(_message_to_dict(final_message))


if __name__ == "__main__":
    app()
