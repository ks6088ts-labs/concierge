from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from concierge.chat.infrastructure.ai.foundry_responder import (
    FoundryChatbotResponder,
    _extract_text,
)


def test_extract_text_from_string() -> None:
    assert _extract_text("hello") == "hello"


def test_extract_text_from_empty_string() -> None:
    assert _extract_text("") == ""


def test_extract_text_from_empty_list() -> None:
    assert _extract_text([]) == ""


def test_extract_text_skips_reasoning_blocks() -> None:
    content = [
        {
            "id": "rs_1",
            "summary": [],
            "type": "reasoning",
            "response_id": "resp_1",
            "index": 0,
        },
        {"type": "text", "text": "Hello", "index": 1},
        {"type": "text", "text": ", world", "index": 1},
        {"type": "text", "text": "!", "id": "msg_1", "index": 1},
    ]
    assert _extract_text(content) == "Hello, world!"


def test_extract_text_concatenates_text_blocks() -> None:
    content = [
        {"type": "text", "text": "こん"},
        {"type": "text", "text": "にちは"},
    ]
    assert _extract_text(content) == "こんにちは"


def test_extract_text_supports_string_blocks() -> None:
    content = ["foo", {"type": "text", "text": "bar"}]
    assert _extract_text(content) == "foobar"


def test_extract_text_ignores_unknown_block_types() -> None:
    content = [
        {"type": "image_url", "image_url": {"url": "http://example.com/x.png"}},
        {"type": "text", "text": "ok"},
    ]
    assert _extract_text(content) == "ok"


def test_extract_text_handles_non_string_text_value() -> None:
    content = [{"type": "text", "text": None}, {"type": "text", "text": "valid"}]
    assert _extract_text(content) == "valid"


def test_extract_text_returns_empty_for_unsupported_type() -> None:
    assert _extract_text(None) == ""
    assert _extract_text(42) == ""


def test_stream_reply_passes_trace_config(monkeypatch) -> None:
    class FakeChatModel:
        def stream(self, messages, config=None):  # noqa: ANN001
            _ = messages
            assert config is not None
            assert len(config["callbacks"]) == 1
            yield SimpleNamespace(content="ok")

    monkeypatch.setattr(
        "concierge.chat.infrastructure.ai.foundry_responder.init_chat_model",
        lambda *_args, **_kwargs: FakeChatModel(),
    )
    monkeypatch.setattr(
        "concierge.chat.infrastructure.ai.foundry_responder.trace_config",
        lambda _service_name: {"callbacks": [object()]},
    )

    responder = FoundryChatbotResponder(model="azure_ai:gpt-5", system_prompt="system")
    chunks = list(responder.stream_reply(conversation=cast(Any, SimpleNamespace()), history=[]))
    assert chunks == ["ok"]
