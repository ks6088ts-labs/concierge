from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from concierge.knowledge.domain.entities import KnowledgeSearchResult
from concierge.knowledge.domain.value_objects import CollectionName
from concierge.knowledge.infrastructure.cli import app as cli_module
from concierge.knowledge.infrastructure.cli.app import app

runner = CliRunner()


def test_cli_help_includes_ingest_and_observability_flags() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "ingest" in result.output
    assert "search" in result.output
    assert "tracing" in result.output
    assert "mlflow" in result.output
    assert "verbose" in result.output


class _StubRepository:
    def __init__(self, results: list[KnowledgeSearchResult]) -> None:
        self._results = results
        self.search_calls: list[tuple[CollectionName, str, int]] = []

    def upsert_chunks(self, chunks):  # pragma: no cover - unused
        return len(chunks)

    def count_chunks(self, collection):  # pragma: no cover - unused
        return len(self._results)

    def drop_collection(self, collection):  # pragma: no cover - unused
        return None

    def search(self, collection, query, k=4):
        self.search_calls.append((collection, query, k))
        return list(self._results)


@pytest.fixture
def _patch_search(monkeypatch: pytest.MonkeyPatch) -> _StubRepository:
    repository = _StubRepository(
        results=[
            KnowledgeSearchResult(
                id="demo:docs/a.md:0:abc123",
                content="hello world from a.md " * 30,
                metadata={"source": "docs/a.md", "chunk_index": 0, "collection": "demo"},
            ),
            KnowledgeSearchResult(
                id="demo:docs/b.md:1:def456",
                content="another chunk",
                metadata={"source": "docs/b.md", "chunk_index": 1, "collection": "demo"},
            ),
        ]
    )
    monkeypatch.setattr(cli_module, "get_knowledge_repository", lambda **_kwargs: repository)
    monkeypatch.setattr(cli_module, "create_embeddings", lambda: object())
    return repository


def test_search_run_prints_human_readable_results(_patch_search: _StubRepository) -> None:
    result = runner.invoke(
        app,
        ["search", "run", "--collection", "demo", "--k", "2", "--snippet", "20", "vector store"],
    )
    assert result.exit_code == 0, result.output
    assert "collection=demo" in result.output
    assert "hits=2" in result.output
    assert "docs/a.md" in result.output
    assert "docs/b.md" in result.output
    assert "..." in result.output  # snippet truncation marker
    assert _patch_search.search_calls == [(CollectionName("demo"), "vector store", 2)]


def test_search_run_emits_json_when_requested(_patch_search: _StubRepository) -> None:
    result = runner.invoke(
        app,
        ["search", "run", "--collection", "demo", "--json", "vector store"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert [item["metadata"]["source"] for item in payload] == ["docs/a.md", "docs/b.md"]


def test_search_run_reports_when_no_results(monkeypatch: pytest.MonkeyPatch) -> None:
    repository = _StubRepository(results=[])
    monkeypatch.setattr(cli_module, "get_knowledge_repository", lambda **_kwargs: repository)
    monkeypatch.setattr(cli_module, "create_embeddings", lambda: object())

    result = runner.invoke(app, ["search", "run", "--collection", "demo", "nothing matches"])

    assert result.exit_code == 0, result.output
    assert "no results" in result.output
