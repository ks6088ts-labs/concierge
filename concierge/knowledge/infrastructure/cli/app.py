from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from dotenv import load_dotenv

from concierge.knowledge.application.use_cases import DeleteCollection, IngestMarkdown
from concierge.knowledge.domain.value_objects import CollectionName
from concierge.knowledge.infrastructure.embeddings.factory import create_embeddings
from concierge.knowledge.infrastructure.loaders.markdown import load_markdown_documents, split_documents
from concierge.knowledge.infrastructure.persistence.factory import get_knowledge_repository
from concierge.loggers import enable_verbose_logging
from concierge.observability import disable_tracing, enable_mlflow, enable_tracing
from concierge.settings import KnowledgeTarget, get_knowledge_settings

app = typer.Typer(add_completion=False, help="Knowledge CLI")
ingest_app = typer.Typer(help="Markdown ingest commands")
app.add_typer(ingest_app, name="ingest")


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


if __name__ == "__main__":
    app()
