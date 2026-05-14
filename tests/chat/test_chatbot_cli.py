from __future__ import annotations

import json
import uuid
from unittest.mock import patch

from typer.testing import CliRunner

from concierge.chat.application.use_cases import CreateConversationUseCase, PostMessageUseCase
from concierge.chat.domain.entities import Conversation, Message
from concierge.chat.domain.value_objects import MessageRole, Participant, ParticipantKind
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


def test_message_reply_bot_disabled() -> None:
    """When bot is disabled (NullChatbotResponder), message reply exits with error code 1."""
    conversation_repo, message_repo, conversation_id = _setup_conversation()

    with (
        patch("concierge.chat.infrastructure.cli.app.get_conversation_repository", return_value=conversation_repo),
        patch("concierge.chat.infrastructure.cli.app.get_message_repository", return_value=message_repo),
    ):
        result = runner.invoke(app, ["message", "reply", str(conversation_id)])

    assert result.exit_code == 1
    # No AGENT message should be saved
    messages = message_repo.find_by_conversation(conversation_id)
    agent_messages = [m for m in messages if m.role == MessageRole.AGENT]
    assert len(agent_messages) == 0


def test_message_reply_bot_enabled() -> None:
    """When bot is enabled (fake responder), message reply succeeds and saves AGENT message."""
    conversation_repo, message_repo, conversation_id = _setup_conversation()

    class FakeResponder:
        def generate_reply(self, conversation: Conversation, history: list[Message]) -> str:
            return "こんにちは！"

    with (
        patch("concierge.chat.infrastructure.cli.app.get_conversation_repository", return_value=conversation_repo),
        patch("concierge.chat.infrastructure.cli.app.get_message_repository", return_value=message_repo),
        patch("concierge.chat.infrastructure.cli.app.create_chatbot_responder", return_value=FakeResponder()),
    ):
        result = runner.invoke(app, ["message", "reply", str(conversation_id)])

    assert result.exit_code == 0

    # Verify the AGENT message was persisted
    messages = message_repo.find_by_conversation(conversation_id)
    agent_messages = [m for m in messages if m.role == MessageRole.AGENT]
    assert len(agent_messages) == 1
    assert agent_messages[0].content == "こんにちは！"
    assert agent_messages[0].sender.kind == ParticipantKind.AGENT

    # Verify JSON output via the CLI runner (may appear in result.output or captured stdout)
    output = result.output.strip() if result.output.strip() else ""
    if output:
        data = json.loads(output)
        assert data["role"] == "AGENT"
        assert data["content"] == "こんにちは！"
