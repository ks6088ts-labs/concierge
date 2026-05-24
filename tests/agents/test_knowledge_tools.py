from __future__ import annotations

import json
from collections.abc import Generator

import pytest
from copilot.tools import ToolInvocation

from concierge.agents.infrastructure.registry_factory import get_agent_registry
from concierge.agents.infrastructure.tools.knowledge_copilot import (
    build_knowledge_copilot_sdk_tool_builders,
)
from concierge.agents.infrastructure.tools.knowledge_langchain import (
    build_knowledge_langchain_tool_builders,
)
from concierge.agents.infrastructure.tools.knowledge_maf import build_knowledge_maf_tool_builders
from concierge.settings.agents_knowledge import AgentsKnowledgeSettings, get_agents_knowledge_settings


class _FakeUseCase:
    def __init__(self, results: list[object] | Exception):
        self._results = results

    def execute(self, *, collection: str, query: str, k: int):
        _ = (collection, query, k)
        if isinstance(self._results, Exception):
            raise self._results
        return list(self._results)


class _FakeResult:
    def __init__(self, source: str, chunk_index: int, content: str, *, distance: float):
        self.content = content
        self.metadata = {"source": source, "chunk_index": chunk_index, "distance": distance}


@pytest.fixture(autouse=True)
def _clear_agent_caches() -> Generator[None, None, None]:
    get_agents_knowledge_settings.cache_clear()
    get_agent_registry.cache_clear()
    yield
    get_agents_knowledge_settings.cache_clear()
    get_agent_registry.cache_clear()


def _configure_single_tool(monkeypatch: pytest.MonkeyPatch) -> AgentsKnowledgeSettings:
    monkeypatch.setenv("AGENTS_KNOWLEDGE__TOOLS", "search_docs")
    monkeypatch.setenv("AGENTS_KNOWLEDGE__SEARCH_DOCS__COLLECTION", "docs")
    return AgentsKnowledgeSettings(_env_file=None)  # ty: ignore[unknown-argument]


def test_knowledge_builder_description_is_env_driven(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTS_KNOWLEDGE__TOOLS", "search_docs")
    monkeypatch.setenv("AGENTS_KNOWLEDGE__SEARCH_DOCS__COLLECTION", "docs")
    monkeypatch.setenv("AGENTS_KNOWLEDGE__SEARCH_DOCS__DESCRIPTION", "Search docs quickly")
    settings = AgentsKnowledgeSettings(_env_file=None)  # ty: ignore[unknown-argument]

    tool = build_knowledge_langchain_tool_builders(settings)[0]({})

    assert tool.description == "Search docs quickly"


def test_knowledge_settings_reject_invalid_tool_names(monkeypatch: pytest.MonkeyPatch) -> None:
    invalid_values = [
        "Search Docs",
        "search-docs",
        "search__docs",
        "search_docs,search_docs",
        "echo",
        "read_file",
        "shell_exec",
        f"{'a' * 51}",
    ]
    for value in invalid_values:
        monkeypatch.setenv("AGENTS_KNOWLEDGE__TOOLS", value)
        with pytest.raises(ValueError):
            AgentsKnowledgeSettings(_env_file=None).configured_tools()  # ty: ignore[unknown-argument]


def test_knowledge_tools_are_not_registered_when_tools_env_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTS_KNOWLEDGE__TOOLS", "")
    monkeypatch.setenv("AGENTS_FILE_TOOLS_ENABLED", "")
    monkeypatch.setenv("AGENTS_SHELL_TOOLS_ENABLED", "")

    registry = get_agent_registry()
    langgraph = registry.resolve("langgraph")

    assert len(langgraph._tool_builders) == 2


def test_knowledge_tools_register_multiple_named_builders(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTS_KNOWLEDGE__TOOLS", "search_docs,search_runbooks")
    monkeypatch.setenv("AGENTS_KNOWLEDGE__SEARCH_DOCS__COLLECTION", "docs")
    monkeypatch.setenv("AGENTS_KNOWLEDGE__SEARCH_DOCS__DESCRIPTION", "Search docs")
    monkeypatch.setenv("AGENTS_KNOWLEDGE__SEARCH_RUNBOOKS__COLLECTION", "runbooks")
    monkeypatch.setenv("AGENTS_KNOWLEDGE__SEARCH_RUNBOOKS__DESCRIPTION", "Search runbooks")
    monkeypatch.setenv("AGENTS_FILE_TOOLS_ENABLED", "")
    monkeypatch.setenv("AGENTS_SHELL_TOOLS_ENABLED", "")
    monkeypatch.setattr(
        "concierge.agents.infrastructure.tools.knowledge.get_search_knowledge_use_case",
        lambda _collection: _FakeUseCase([]),
    )

    registry = get_agent_registry()
    langgraph = registry.resolve("langgraph")
    tools = [builder({}) for builder in langgraph._tool_builders]
    names = [tool.name for tool in tools]

    assert "search_docs" in names
    assert "search_runbooks" in names


def test_knowledge_langchain_tool_returns_no_hits_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _configure_single_tool(monkeypatch)
    monkeypatch.setattr(
        "concierge.agents.infrastructure.tools.knowledge.get_search_knowledge_use_case",
        lambda _collection: _FakeUseCase([]),
    )

    tool = build_knowledge_langchain_tool_builders(settings)[0]({})
    payload = json.loads(tool.invoke({"query": "nothing"}))

    assert payload["collection"] == "docs"
    assert payload["hits"] == []
    assert payload["message"] == "No matching knowledge."


def test_knowledge_langchain_tool_returns_error_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _configure_single_tool(monkeypatch)
    monkeypatch.setattr(
        "concierge.agents.infrastructure.tools.knowledge.get_search_knowledge_use_case",
        lambda _collection: _FakeUseCase(RuntimeError("dsn error")),
    )

    tool = build_knowledge_langchain_tool_builders(settings)[0]({})
    payload = json.loads(tool.invoke({"query": "hello"}))

    assert payload["collection"] == "docs"
    assert "knowledge search failed" in payload["error"]


def test_knowledge_langchain_tool_normalizes_score_and_truncates_utf8(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTS_KNOWLEDGE__TOOLS", "search_docs")
    monkeypatch.setenv("AGENTS_KNOWLEDGE__SEARCH_DOCS__COLLECTION", "docs")
    monkeypatch.setenv("AGENTS_KNOWLEDGE__SEARCH_DOCS__MAX_CHARS", "10")
    settings = AgentsKnowledgeSettings(_env_file=None)  # ty: ignore[unknown-argument]
    monkeypatch.setattr(
        "concierge.agents.infrastructure.tools.knowledge.get_search_knowledge_use_case",
        lambda _collection: _FakeUseCase([_FakeResult("docs/a.md", 0, "あいうえおかきくけこさ", distance=0.5)]),
    )

    tool = build_knowledge_langchain_tool_builders(settings)[0]({})
    payload = json.loads(tool.invoke({"query": "hello"}))

    assert payload["truncated"] is True
    assert payload["hits"][0]["content"] == "あいうえおかきくけこ…"
    assert 0.0 <= payload["hits"][0]["score"] <= 1.0


@pytest.mark.anyio
async def test_knowledge_builder_parity_across_sdks(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _configure_single_tool(monkeypatch)
    results = [
        _FakeResult("docs/a.md", 0, "A", distance=0.1),
        _FakeResult("docs/b.md", 2, "B", distance=0.3),
    ]
    monkeypatch.setattr(
        "concierge.agents.infrastructure.tools.knowledge.get_search_knowledge_use_case",
        lambda _collection: _FakeUseCase(results),
    )

    langchain_tool = build_knowledge_langchain_tool_builders(settings)[0]({})
    maf_tool = build_knowledge_maf_tool_builders(settings)[0]({})
    copilot_tool = build_knowledge_copilot_sdk_tool_builders(settings)[0]({})

    payload_langchain = json.loads(langchain_tool.invoke({"query": "q", "k": 2}))
    payload_maf = json.loads(maf_tool("q", 2))
    copilot_result = await copilot_tool.handler(
        ToolInvocation(
            session_id="s1",
            tool_call_id="tc1",
            tool_name="search_docs",
            arguments={"query": "q", "k": 2},
        )
    )
    payload_copilot = json.loads(copilot_result.text_result_for_llm)

    expected = {("docs/a.md", 0), ("docs/b.md", 2)}
    assert {(hit["source"], hit["chunk_index"]) for hit in payload_langchain["hits"]} == expected
    assert {(hit["source"], hit["chunk_index"]) for hit in payload_maf["hits"]} == expected
    assert {(hit["source"], hit["chunk_index"]) for hit in payload_copilot["hits"]} == expected
