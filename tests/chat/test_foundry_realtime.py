"""Tests for FoundryRealtimeResponder URL derivation logic."""

from __future__ import annotations

import pytest

from concierge.chat.infrastructure.ai.factory import ChatbotNotConfiguredError
from concierge.chat.infrastructure.ai.foundry_realtime import (
    FoundryRealtimeResponder,
    _derive_wss_host,
    build_turn_detection,
)

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


# ---------------------------------------------------------------------------
# build_turn_detection unit tests
# ---------------------------------------------------------------------------


def test_server_vad_includes_tuning_params() -> None:
    td = build_turn_detection(
        "server_vad",
        threshold=0.6,
        prefix_padding_ms=250,
        silence_duration_ms=900,
        create_response=True,
        interrupt_response=True,
    )
    assert td == {
        "type": "server_vad",
        "threshold": 0.6,
        "prefix_padding_ms": 250,
        "silence_duration_ms": 900,
        "create_response": True,
        "interrupt_response": True,
    }


def test_server_vad_is_the_default_for_unknown_type() -> None:
    td = build_turn_detection("something-else")
    assert td is not None
    assert td["type"] == "server_vad"


def test_semantic_vad_uses_eagerness_and_omits_silence_params() -> None:
    td = build_turn_detection(
        "semantic_vad",
        eagerness="low",
        create_response=False,
        interrupt_response=False,
    )
    assert td == {
        "type": "semantic_vad",
        "eagerness": "low",
        "create_response": False,
        "interrupt_response": False,
    }
    assert td is not None
    assert "silence_duration_ms" not in td
    assert "threshold" not in td


@pytest.mark.parametrize("value", ["none", "null", "NONE", "  none  "])
def test_none_disables_turn_detection(value: str) -> None:
    assert build_turn_detection(value) is None


@pytest.mark.parametrize("value", ["", "   "])
def test_empty_type_falls_back_to_server_vad(value: str) -> None:
    """An empty env var means "unset", not push-to-talk, so default to server_vad."""
    td = build_turn_detection(value)
    assert td is not None
    assert td["type"] == "server_vad"


@pytest.mark.parametrize("value", ["SERVER_VAD", "  server_vad ", "Semantic_VAD"])
def test_type_is_case_and_whitespace_insensitive(value: str) -> None:
    td = build_turn_detection(value)
    assert td is not None
    assert td["type"] in {"server_vad", "semantic_vad"}


def test_responder_builds_turn_detection_from_kwargs() -> None:
    responder = FoundryRealtimeResponder(
        endpoint_realtime="https://r.openai.azure.com/",
        deployment="gpt-realtime-1.5",
        voice="alloy",
        locale="ja-JP",
        system_prompt="hi",
        turn_detection_type="semantic_vad",
        vad_eagerness="low",
    )
    assert responder._turn_detection == {
        "type": "semantic_vad",
        "eagerness": "low",
        "create_response": True,
        "interrupt_response": True,
    }


def test_responder_push_to_talk_disables_turn_detection() -> None:
    responder = FoundryRealtimeResponder(
        endpoint_realtime="https://r.openai.azure.com/",
        deployment="gpt-realtime-1.5",
        voice="alloy",
        locale="ja-JP",
        system_prompt="hi",
        turn_detection_type="none",
    )
    assert responder._turn_detection is None
