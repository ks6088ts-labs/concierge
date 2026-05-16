from __future__ import annotations

import uuid
from collections.abc import Iterator
from unittest.mock import patch

from typer.testing import CliRunner

from concierge.chat.application.use_cases import CreateConversationUseCase, PostMessageUseCase
from concierge.chat.domain.entities import Conversation, Message
from concierge.chat.domain.value_objects import MessageRole, Participant, ParticipantKind
from concierge.chat.infrastructure.ai.factory import ChatbotNotConfiguredError
from concierge.chat.infrastructure.cli.app import app
from concierge.chat.infrastructure.persistence.memory import InMemoryConversationRepository, InMemoryMessageRepository

runner = CliRunner()


def _setup_conversation() -> tuple[InMemoryConversationRepository, InMemoryMessageRepository, uuid.UUID]:
    conversation_repo = InMemoryConversationRepository()
    message_repo = InMemoryMessageRepository()
    user = Participant(id=uuid.uuid4(), kind=ParticipantKind.USER, display_name="alice")
    conversation = CreateConversationUseCase(conversation_repo).execute("test", user)
    PostMessageUseCase(conversation_repo, message_repo).execute(conversation.id, user, "hello")
    return conversation_repo, message_repo, conversation.id


def test_message_reply_chatbot_not_configured() -> None:
    """If the chatbot is not configured, the CLI exits with code 1."""
    conversation_repo, message_repo, conversation_id = _setup_conversation()

    def _raise() -> object:
        raise ChatbotNotConfiguredError("AZURE_AI_PROJECT_ENDPOINT is not configured")

    with (
        patch("concierge.chat.infrastructure.cli.app.get_conversation_repository", return_value=conversation_repo),
        patch("concierge.chat.infrastructure.cli.app.get_message_repository", return_value=message_repo),
        patch("concierge.chat.infrastructure.cli.app.create_chatbot_responder", side_effect=_raise),
    ):
        result = runner.invoke(app, ["message", "reply", str(conversation_id)])

    assert result.exit_code == 1
    agent_messages = [m for m in message_repo.find_by_conversation(conversation_id) if m.role == MessageRole.AGENT]
    assert agent_messages == []


def test_cli_help_includes_observability_options() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "tracing" in result.output
    assert "mlflow" in result.output
    assert "verbose" in result.output


def test_message_reply_streams_and_persists() -> None:
    """With a configured responder, ``message reply`` streams chunks and saves the AGENT message."""
    conversation_repo, message_repo, conversation_id = _setup_conversation()

    class FakeResponder:
        def stream_reply(self, conversation: Conversation, history: list[Message]) -> Iterator[str]:
            yield from ["こん", "にちは", "！"]

    with (
        patch("concierge.chat.infrastructure.cli.app.get_conversation_repository", return_value=conversation_repo),
        patch("concierge.chat.infrastructure.cli.app.get_message_repository", return_value=message_repo),
        patch("concierge.chat.infrastructure.cli.app.create_chatbot_responder", return_value=FakeResponder()),
    ):
        result = runner.invoke(app, ["message", "reply", str(conversation_id)])

    assert result.exit_code == 0
    # Streamed chunks appear in the output
    assert "こんにちは！" in result.output

    agent_messages = [m for m in message_repo.find_by_conversation(conversation_id) if m.role == MessageRole.AGENT]
    assert len(agent_messages) == 1
    assert agent_messages[0].content == "こんにちは！"
    assert agent_messages[0].sender.kind == ParticipantKind.AGENT
