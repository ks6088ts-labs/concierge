"""Tests for AgentChatbotResponder and related factory integration."""

from __future__ import annotations

import uuid
from typing import ClassVar

import pytest

from concierge.agents.application.contracts import AgentRequest, AgentResponse
from concierge.chat.infrastructure.ai.agent_responder import AgentChatbotResponder
from concierge.chat.infrastructure.ai.exceptions import ChatbotNotConfiguredError

# ---------------------------------------------------------------------------
# Minimal mock agent
# ---------------------------------------------------------------------------


class _MockAgent:
    agent_type: ClassVar[str] = "mock"

    def __init__(self, response: AgentResponse) -> None:
        self._response = response

    async def handle(self, request: AgentRequest) -> AgentResponse:
        return self._response


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_conversation():
    from concierge.chat.domain.entities import Conversation

    return Conversation(title="test", id=uuid.uuid4())


def _make_user_message(content: str = "hello"):
    from concierge.chat.domain.entities import Message
    from concierge.chat.domain.value_objects import MessageRole, Participant, ParticipantKind

    conv_id = uuid.uuid4()
    sender = Participant(id=uuid.uuid4(), kind=ParticipantKind.USER, display_name="User")
    return Message(conversation_id=conv_id, sender=sender, content=content, role=MessageRole.USER)


# ---------------------------------------------------------------------------
# Tests: AgentChatbotResponder
# ---------------------------------------------------------------------------


def test_stream_reply_success() -> None:
    response = AgentResponse(status="succeeded", result={"reply": "hi"})
    agent = _MockAgent(response)
    responder = AgentChatbotResponder(agent)

    conversation = _make_conversation()
    history = [_make_user_message("hello")]

    chunks = list(responder.stream_reply(conversation, history))
    assert chunks == ["hi"]


def test_stream_reply_uses_echo_field_fallback() -> None:
    response = AgentResponse(status="succeeded", result={"echo": "echoed"})
    agent = _MockAgent(response)
    responder = AgentChatbotResponder(agent)

    conversation = _make_conversation()
    history = [_make_user_message("hello")]

    chunks = list(responder.stream_reply(conversation, history))
    assert chunks == ["echoed"]


def test_stream_reply_failed_status_yields_error() -> None:
    response = AgentResponse(status="failed", error="something went wrong")
    agent = _MockAgent(response)
    responder = AgentChatbotResponder(agent)

    conversation = _make_conversation()
    history = [_make_user_message("hello")]

    chunks = list(responder.stream_reply(conversation, history))
    assert chunks == ["something went wrong"]


def test_stream_reply_failed_no_error_yields_fallback() -> None:
    response = AgentResponse(status="failed", error=None)
    agent = _MockAgent(response)
    responder = AgentChatbotResponder(agent)

    conversation = _make_conversation()
    history = [_make_user_message("hello")]

    chunks = list(responder.stream_reply(conversation, history))
    assert chunks == ["(agent returned failed status)"]


def test_stream_reply_empty_history() -> None:
    response = AgentResponse(status="succeeded", result={"reply": "no user message"})
    agent = _MockAgent(response)
    responder = AgentChatbotResponder(agent)

    conversation = _make_conversation()
    chunks = list(responder.stream_reply(conversation, []))
    assert chunks == ["no user message"]


# ---------------------------------------------------------------------------
# Tests: create_chatbot_responder factory
# ---------------------------------------------------------------------------


def test_create_chatbot_responder_returns_agent_responder(monkeypatch: pytest.MonkeyPatch) -> None:
    """With CHAT_BOT_AGENT_TYPE=echo, factory returns an AgentChatbotResponder."""
    monkeypatch.delenv("CHAT_RESPONDER_BACKEND", raising=False)
    monkeypatch.setenv("CHAT_BOT_AGENT_TYPE", "echo")

    from concierge.agents.infrastructure.registry_factory import get_agent_registry
    from concierge.chat.infrastructure.ai import factory as factory_module
    from concierge.settings import chat as chat_settings_module

    # Clear lru_caches
    chat_settings_module.get_chat_settings.cache_clear()
    get_agent_registry.cache_clear()

    responder = factory_module.create_chatbot_responder()
    assert isinstance(responder, AgentChatbotResponder)

    # Cleanup
    chat_settings_module.get_chat_settings.cache_clear()
    get_agent_registry.cache_clear()


def test_create_chatbot_responder_unknown_agent_type_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """With CHAT_BOT_AGENT_TYPE set to an unregistered type, ChatbotNotConfiguredError is raised."""
    monkeypatch.delenv("CHAT_RESPONDER_BACKEND", raising=False)
    monkeypatch.setenv("CHAT_BOT_AGENT_TYPE", "nonexistent-agent")

    from concierge.agents.infrastructure.registry_factory import get_agent_registry
    from concierge.chat.infrastructure.ai import factory as factory_module
    from concierge.settings import chat as chat_settings_module

    chat_settings_module.get_chat_settings.cache_clear()
    get_agent_registry.cache_clear()

    with pytest.raises(ChatbotNotConfiguredError):
        factory_module.create_chatbot_responder()

    # Cleanup
    chat_settings_module.get_chat_settings.cache_clear()
    get_agent_registry.cache_clear()


def test_create_chatbot_responder_foundry_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """CHAT_BOT_AGENT_TYPE=foundry builds a FoundryChatbotResponder when endpoint settings are populated."""
    monkeypatch.delenv("CHAT_RESPONDER_BACKEND", raising=False)
    monkeypatch.setenv("CHAT_BOT_AGENT_TYPE", "foundry")

    from concierge.chat.infrastructure.ai import factory as factory_module
    from concierge.chat.infrastructure.ai.foundry_responder import FoundryChatbotResponder
    from concierge.settings import chat as chat_settings_module
    from concierge.settings.microsoft_foundry import MicrosoftFoundrySettings

    chat_settings_module.get_chat_settings.cache_clear()
    # Inject an in-memory Foundry settings instance so the test is independent
    # of the developer's local .env (which may or may not have the endpoint set).
    populated = MicrosoftFoundrySettings(
        _env_file=None,  # ty: ignore[unknown-argument]
        azure_ai_project_endpoint="https://example.invalid/api/projects/test",
    )
    monkeypatch.setattr(factory_module, "get_microsoft_foundry_settings", lambda: populated)

    responder = factory_module.create_chatbot_responder()
    assert isinstance(responder, FoundryChatbotResponder)

    chat_settings_module.get_chat_settings.cache_clear()


def test_create_chatbot_responder_foundry_missing_endpoint_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """CHAT_BOT_AGENT_TYPE=foundry without AZURE_AI_PROJECT_ENDPOINT raises ChatbotNotConfiguredError."""
    monkeypatch.delenv("CHAT_RESPONDER_BACKEND", raising=False)
    monkeypatch.setenv("CHAT_BOT_AGENT_TYPE", "foundry")

    from concierge.chat.infrastructure.ai import factory as factory_module
    from concierge.settings import chat as chat_settings_module
    from concierge.settings.microsoft_foundry import MicrosoftFoundrySettings

    chat_settings_module.get_chat_settings.cache_clear()
    # Inject an empty endpoint so the test is independent of the developer's .env.
    empty = MicrosoftFoundrySettings(
        _env_file=None,  # ty: ignore[unknown-argument]
        azure_ai_project_endpoint="",
    )
    monkeypatch.setattr(factory_module, "get_microsoft_foundry_settings", lambda: empty)

    with pytest.raises(ChatbotNotConfiguredError):
        factory_module.create_chatbot_responder()

    chat_settings_module.get_chat_settings.cache_clear()


def test_legacy_responder_backend_env_emits_deprecation_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    """Setting the obsolete CHAT_RESPONDER_BACKEND env var should emit a DeprecationWarning."""
    monkeypatch.setenv("CHAT_RESPONDER_BACKEND", "agent")
    monkeypatch.setenv("CHAT_BOT_AGENT_TYPE", "echo")

    from concierge.agents.infrastructure.registry_factory import get_agent_registry
    from concierge.chat.infrastructure.ai import factory as factory_module
    from concierge.settings import chat as chat_settings_module

    chat_settings_module.get_chat_settings.cache_clear()
    get_agent_registry.cache_clear()
    # Reset the module-level flag so the warning is emitted within this test.
    factory_module._legacy_warning_emitted = False

    with pytest.warns(DeprecationWarning, match="CHAT_RESPONDER_BACKEND"):
        factory_module.create_chatbot_responder()

    chat_settings_module.get_chat_settings.cache_clear()
    get_agent_registry.cache_clear()
    factory_module._legacy_warning_emitted = False
