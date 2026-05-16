"""Tests for FoundryRealtimeResponder URL derivation logic."""

from __future__ import annotations

import pytest

from concierge.chat.infrastructure.ai.factory import ChatbotNotConfiguredError
from concierge.chat.infrastructure.ai.foundry_realtime import _derive_wss_host

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
