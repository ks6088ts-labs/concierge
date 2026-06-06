from __future__ import annotations

from typing import Any

import pytest

from concierge.chat.infrastructure.ai import realtime_knowledge
from concierge.settings import get_agents_knowledge_settings


def _clear_settings_and_adapter_cache() -> None:
    get_agents_knowledge_settings.cache_clear()
    realtime_knowledge.get_realtime_knowledge_tool_adapter.cache_clear()


def test_tool_definitions_empty_when_no_knowledge_tool_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTS_KNOWLEDGE__TOOLS", "")
    monkeypatch.delenv("AGENTS_KNOWLEDGE__SEARCH_DOCS__COLLECTION", raising=False)
    _clear_settings_and_adapter_cache()

    assert realtime_knowledge.get_realtime_tool_definitions() == []
    assert realtime_knowledge.get_realtime_tool_executor() is None


def test_executor_runs_knowledge_search_with_validated_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTS_KNOWLEDGE__TOOLS", "search_docs")
    monkeypatch.setenv("AGENTS_KNOWLEDGE__SEARCH_DOCS__COLLECTION", "knowledge_default")
    monkeypatch.setenv("AGENTS_KNOWLEDGE__SEARCH_DOCS__DESCRIPTION", "Search docs")
    _clear_settings_and_adapter_cache()

    captured: dict[str, Any] = {}

    def _fake_search_knowledge_chunks(
        *,
        config,  # noqa: ANN001
        query: str,
        k: int | None,
        tool_name: str,
    ) -> str:
        captured["config_name"] = config.name
        captured["query"] = query
        captured["k"] = k
        captured["tool_name"] = tool_name
        return '{"hits":[],"truncated":false}'

    monkeypatch.setattr(realtime_knowledge, "search_knowledge_chunks", _fake_search_knowledge_chunks)

    definitions = realtime_knowledge.get_realtime_tool_definitions()
    executor = realtime_knowledge.get_realtime_tool_executor()
    assert len(definitions) == 1
    assert definitions[0]["name"] == "search_docs"
    assert executor is not None

    output = executor("search_docs", {"query": "What is concierge?", "k": 3})

    assert output == '{"hits":[],"truncated":false}'
    assert captured == {
        "config_name": "search_docs",
        "query": "What is concierge?",
        "k": 3,
        "tool_name": "search_docs",
    }
