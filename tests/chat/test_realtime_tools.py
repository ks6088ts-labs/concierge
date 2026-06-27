from __future__ import annotations

from collections.abc import Generator

import pytest

from concierge.chat.infrastructure.ai.realtime_tools import build_default_realtime_tools
from concierge.settings.agents_knowledge import get_agents_knowledge_settings


@pytest.fixture(autouse=True)
def _clear_knowledge_settings_cache() -> Generator[None, None, None]:
    get_agents_knowledge_settings.cache_clear()
    yield
    get_agents_knowledge_settings.cache_clear()


def test_default_realtime_tools_without_knowledge(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTS_KNOWLEDGE__TOOLS", "")
    tools = build_default_realtime_tools()
    names = {tool.name for tool in tools}

    assert "get_current_time" in names
    assert "echo" in names
    assert "read_file" in names
    assert "list_directory" in names
    assert "file_search" in names
    assert "search_docs" not in names


def test_realtime_tools_include_configured_knowledge_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTS_KNOWLEDGE__TOOLS", "search_docs")
    monkeypatch.setenv("AGENTS_KNOWLEDGE__SEARCH_DOCS__COLLECTION", "docs")
    monkeypatch.setenv("AGENTS_KNOWLEDGE__SEARCH_DOCS__DESCRIPTION", "Search docs collection")
    monkeypatch.setattr(
        "concierge.agents.infrastructure.tools.knowledge_langchain.search_knowledge_chunks",
        lambda **_kwargs: '{"collection":"docs","hits":[]}',
    )

    tools = {tool.name: tool for tool in build_default_realtime_tools()}

    assert "search_docs" in tools
    assert tools["search_docs"].description == "Search docs collection"
    assert tools["search_docs"].handler({"query": "how to deploy"}) == '{"collection":"docs","hits":[]}'
