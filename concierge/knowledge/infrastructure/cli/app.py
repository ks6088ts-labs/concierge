from __future__ import annotations

from contextlib import AbstractContextManager, nullcontext
from pathlib import Path
from typing import Annotated

import typer
from dotenv import load_dotenv

from concierge.knowledge.application.use_cases import DeleteCollection, IngestMarkdown, SearchKnowledge
from concierge.knowledge.domain.value_objects import CollectionName
from concierge.knowledge.infrastructure.embeddings.factory import create_embeddings
from concierge.knowledge.infrastructure.loaders.markdown import load_markdown_documents, split_documents
from concierge.knowledge.infrastructure.persistence.factory import get_knowledge_repository
from concierge.loggers import enable_verbose_logging
from concierge.observability import disable_tracing, enable_mlflow, enable_tracing, is_mlflow_enabled
from concierge.settings import KnowledgeTarget, get_knowledge_settings

app = typer.Typer(add_completion=False, help="Knowledge CLI")
ingest_app = typer.Typer(help="Markdown ingest commands")
search_app = typer.Typer(help="Knowledge search commands")


def _ingest_trace_span(name: str, **attributes: object) -> AbstractContextManager[object]:
    """Return an MLflow parent span (or a no-op) so embedding traces are grouped.

    Embeddings.embed_documents() bypasses LangChain's CallbackManager and is
    only captured by mlflow.openai.autolog(). Without a surrounding span each
    embedding HTTP request becomes its own root trace in the MLflow UI, which
    is noisy. Opening a parent span here nests them all under one trace per
    CLI invocation. Falls back to nullcontext when MLflow is not enabled so
    the CLI never imports mlflow unnecessarily.
    """
    if not is_mlflow_enabled():
        return nullcontext()
    import mlflow

    return mlflow.start_span(name=name, attributes=attributes)


app.add_typer(ingest_app, name="ingest")
app.add_typer(search_app, name="search")


@app.callback()
def _bootstrap(
    tracing: Annotated[bool, typer.Option("--tracing", "-t", help="Enable tracing")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose logging")] = False,
    mlflow: Annotated[bool, typer.Option("--mlflow", "-m", help="Enable MLflow autologging")] = False,
) -> None:
    load_dotenv()
    if tracing:
        enable_tracing()
    else:
        disable_tracing()
    if verbose:
        enable_verbose_logging()
    if mlflow:
        enable_mlflow()


@ingest_app.command("run")
def ingest_run(
    paths: Annotated[list[Path], typer.Argument(help="Markdown file(s) or directory path(s)")],
    collection: Annotated[
        str,
        typer.Option("--collection", help="Collection/table name"),
    ] = "",
    target: Annotated[
        KnowledgeTarget,
        typer.Option("--target", help="PostgreSQL target (docker|azure)", case_sensitive=False),
    ] = KnowledgeTarget.DOCKER,
) -> None:
    settings = get_knowledge_settings()
    resolved_collection = CollectionName(collection or settings.default_collection)
    with _ingest_trace_span(
        "knowledge.ingest.run",
        collection=str(resolved_collection),
        target=target.value,
        paths=[str(p) for p in paths],
    ):
        repository = get_knowledge_repository(
            collection=resolved_collection,
            target=target,
            embeddings=create_embeddings(),
            ensure_collection=True,
        )
        result = IngestMarkdown(
            repository=repository,
            loader=load_markdown_documents,
            splitter=split_documents,
        ).execute(paths=paths, collection=resolved_collection)
    typer.echo(
        "ingest completed: "
        f"files={result.files_processed} chunks={result.chunks_processed} records={result.records_in_collection}"
    )


@ingest_app.command("stats")
def ingest_stats(
    collection: Annotated[
        str,
        typer.Option("--collection", help="Collection/table name"),
    ] = "",
    target: Annotated[
        KnowledgeTarget,
        typer.Option("--target", help="PostgreSQL target (docker|azure)", case_sensitive=False),
    ] = KnowledgeTarget.DOCKER,
) -> None:
    settings = get_knowledge_settings()
    resolved_collection = CollectionName(collection or settings.default_collection)
    repository = get_knowledge_repository(
        collection=resolved_collection,
        target=target,
    )
    count = repository.count_chunks(resolved_collection)
    typer.echo(f"collection={resolved_collection} records={count}")


@ingest_app.command("drop")
def ingest_drop(
    collection: Annotated[
        str,
        typer.Option("--collection", help="Collection/table name"),
    ] = "",
    target: Annotated[
        KnowledgeTarget,
        typer.Option("--target", help="PostgreSQL target (docker|azure)", case_sensitive=False),
    ] = KnowledgeTarget.DOCKER,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    settings = get_knowledge_settings()
    resolved_collection = CollectionName(collection or settings.default_collection)
    if not yes:
        typer.confirm(f"Drop knowledge collection '{resolved_collection}'?", abort=True)
    repository = get_knowledge_repository(
        collection=resolved_collection,
        target=target,
    )
    result = DeleteCollection(repository).execute(resolved_collection)
    typer.echo(f"dropped collection={result.collection}")


@search_app.command("run")
def search_run(
    query: Annotated[str, typer.Argument(help="Query text")],
    collection: Annotated[
        str,
        typer.Option("--collection", help="Collection/table name"),
    ] = "",
    target: Annotated[
        KnowledgeTarget,
        typer.Option("--target", help="PostgreSQL target (docker|azure)", case_sensitive=False),
    ] = KnowledgeTarget.DOCKER,
    k: Annotated[int, typer.Option("--k", "-k", min=1, help="Number of results to return")] = 4,
    snippet: Annotated[
        int,
        typer.Option("--snippet", min=0, help="Maximum characters of each chunk to print (0 = full content)"),
    ] = 200,
    json_output: Annotated[bool, typer.Option("--json", help="Emit raw JSON instead of human-readable text")] = False,
) -> None:
    settings = get_knowledge_settings()
    resolved_collection = CollectionName(collection or settings.default_collection)
    repository = get_knowledge_repository(
        collection=resolved_collection,
        target=target,
        embeddings=create_embeddings(),
    )
    results = SearchKnowledge(repository).execute(
        collection=resolved_collection,
        query=query,
        k=k,
    )
    if json_output:
        import json

        payload = [{"id": r.id, "content": r.content, "metadata": r.metadata} for r in results]
        typer.echo(json.dumps(payload, ensure_ascii=False))
        return
    if not results:
        typer.echo(f"no results for collection={resolved_collection} query={query!r}")
        return
    typer.echo(f"collection={resolved_collection} query={query!r} hits={len(results)}")
    for rank, result in enumerate(results, start=1):
        source = result.metadata.get("source", "<unknown>")
        chunk_index = result.metadata.get("chunk_index", "?")
        content = result.content if snippet == 0 else result.content[:snippet]
        if snippet and len(result.content) > snippet:
            content = f"{content}..."
        typer.echo(f"[{rank}] source={source} chunk={chunk_index}")
        typer.echo(content)


if __name__ == "__main__":
    app()
