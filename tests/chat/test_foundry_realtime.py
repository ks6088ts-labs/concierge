"""Tests for FoundryRealtimeResponder URL derivation logic."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest

from concierge.chat.domain.entities import Conversation
from concierge.chat.domain.value_objects import Participant, ParticipantKind
from concierge.chat.infrastructure.ai.factory import ChatbotNotConfiguredError
from concierge.chat.infrastructure.ai.foundry_realtime import FoundryRealtimeResponder, _derive_wss_host

# ---------------------------------------------------------------------------
# _derive_wss_host unit tests
# ---------------------------------------------------------------------------


def test_openai_azure_com_is_kept_as_is() -> None:
    host = _derive_wss_host("https://myresource.openai.azure.com/")
    assert host == "myresource.openai.azure.com"


def test_openai_azure_com_without_trailing_slash() -> None:
    host = _derive_wss_host("https://myresource.openai.azure.com")
    assert host == "myresource.openai.azure.com"


def test_services_ai_azure_com_is_normalised() -> None:
    host = _derive_wss_host("https://myresource.services.ai.azure.com/api/projects/proj123")
    assert host == "myresource.openai.azure.com"


def test_services_ai_azure_com_without_path() -> None:
    host = _derive_wss_host("https://myresource.services.ai.azure.com/")
    assert host == "myresource.openai.azure.com"


def test_empty_string_raises() -> None:
    with pytest.raises(ChatbotNotConfiguredError):
        _derive_wss_host("")


def test_whitespace_only_raises() -> None:
    with pytest.raises(ChatbotNotConfiguredError):
        _derive_wss_host("   ")


def test_http_scheme_raises() -> None:
    with pytest.raises(ChatbotNotConfiguredError):
        _derive_wss_host("http://myresource.openai.azure.com/")


def test_wss_scheme_raises() -> None:
    with pytest.raises(ChatbotNotConfiguredError):
        _derive_wss_host("wss://myresource.openai.azure.com/")


def test_no_scheme_raises() -> None:
    with pytest.raises(ChatbotNotConfiguredError):
        _derive_wss_host("myresource.openai.azure.com")


def test_generic_https_endpoint_kept() -> None:
    """Non-azure hosts that start with https:// should return their host unchanged."""
    host = _derive_wss_host("https://custom.host.example.com/path")
    assert host == "custom.host.example.com"


def test_open_adds_tool_configuration_when_tools_are_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class FakeCredential:
        def get_token(self, _scope: str) -> Any:
            return SimpleNamespace(token="fake-token")

    class FakeSession:
        def __init__(
            self,
            wss_url: str,
            extra_headers: dict[str, str],
            session_config: dict[str, Any],
            initial_items: list[dict[str, Any]] | None = None,
        ) -> None:
            captured["wss_url"] = wss_url
            captured["extra_headers"] = extra_headers
            captured["session_config"] = session_config
            captured["initial_items"] = initial_items

    monkeypatch.setattr("concierge.chat.infrastructure.ai.foundry_realtime.DefaultAzureCredential", FakeCredential)
    monkeypatch.setattr("concierge.chat.infrastructure.ai.foundry_realtime._FoundryRealtimeSession", FakeSession)

    responder = FoundryRealtimeResponder(
        endpoint_realtime="https://myresource.openai.azure.com/",
        deployment="gpt-realtime",
        voice="alloy",
        locale="ja-JP",
        system_prompt="system",
        realtime_tools=[
            {
                "type": "function",
                "name": "search_docs",
                "description": "Search docs",
                "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
            }
        ],
    )
    conversation = Conversation(
        title="test",
        participants=[
            Participant(
                id=uuid.uuid4(),
                kind=ParticipantKind.USER,
                display_name="alice",
            )
        ],
    )

    responder.open(conversation, history=[])

    assert captured["wss_url"] == "wss://myresource.openai.azure.com/openai/v1/realtime?model=gpt-realtime"
    assert captured["extra_headers"]["Authorization"].startswith("Bearer ")
    assert captured["session_config"]["tool_choice"] == "auto"
    assert captured["session_config"]["tools"] == [
        {
            "type": "function",
            "name": "search_docs",
            "description": "Search docs",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        }
    ]


def test_open_does_not_add_tool_configuration_when_tools_are_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class FakeCredential:
        def get_token(self, _scope: str) -> Any:
            return SimpleNamespace(token="fake-token")

    class FakeSession:
        def __init__(
            self,
            _wss_url: str,
            _extra_headers: dict[str, str],
            session_config: dict[str, Any],
            _initial_items: list[dict[str, Any]] | None = None,
        ) -> None:
            captured["session_config"] = session_config

    monkeypatch.setattr("concierge.chat.infrastructure.ai.foundry_realtime.DefaultAzureCredential", FakeCredential)
    monkeypatch.setattr("concierge.chat.infrastructure.ai.foundry_realtime._FoundryRealtimeSession", FakeSession)

    responder = FoundryRealtimeResponder(
        endpoint_realtime="https://myresource.openai.azure.com/",
        deployment="gpt-realtime",
        voice="alloy",
        locale="ja-JP",
        system_prompt="system",
    )
    conversation = Conversation(
        title="test",
        participants=[
            Participant(
                id=uuid.uuid4(),
                kind=ParticipantKind.USER,
                display_name="alice",
            )
        ],
    )

    responder.open(conversation, history=[])

    assert "tools" not in captured["session_config"]
    assert "tool_choice" not in captured["session_config"]
