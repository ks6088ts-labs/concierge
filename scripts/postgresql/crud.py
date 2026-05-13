"""CRUD CLI for the local pgvector PostgreSQL service.

The script demonstrates how to use the LangChain `langchain-postgres` integration
to manage a vector store backed by ``pgvector`` running in Docker (see
``compose.yml``). The defaults align with the embedding deployment used by
``scripts/microsoft_foundry/vanilla.py`` (``text-embedding-3-small`` returning
1536-dimensional vectors).

Usage::

    # Start the local PostgreSQL service first
    docker compose up -d postgres

    # Create the table, bulk-insert sample documents, search, then drop
    uv run python scripts/postgresql/crud.py create-table
    uv run python scripts/postgresql/crud.py bulk-create
    uv run python scripts/postgresql/crud.py search --query "fruit"
    uv run python scripts/postgresql/crud.py drop-table
"""

import logging
import uuid
from functools import lru_cache
from typing import Annotated

import typer
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from concierge.loggers import get_logger
from concierge.settings import get_microsoft_foundry_settings, get_postgres_settings

DEFAULT_SETTINGS = {
    "embedding_model": "text-embedding-3-small",
    # ``text-embedding-3-small`` returns 1536-dimensional vectors. Override with
    # ``--vector-size`` if you switch to a model that uses a different dimension
    # (for example, ``text-embedding-3-large`` returns 3072).
    "vector_size": 1536,
    "table_name": "concierge_docs",
}

app = typer.Typer(
    add_completion=False,
    help="PostgreSQL (pgvector) CRUD CLI for the LangChain vector store",
)

logger = get_logger(__name__)

# Module-level state set by the global ``--fake-embeddings`` flag.
_fake_embeddings_enabled: bool = False


@app.callback()
def _global_options(
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose (DEBUG) logging",
        ),
    ] = False,
    fake_embeddings: Annotated[
        bool,
        typer.Option(
            "--fake-embeddings",
            "-f",
            help=(
                "Use ``DeterministicFakeEmbedding`` instead of Microsoft Foundry. "
                "Handy for purely-local testing without Azure credentials."
            ),
        ),
    ] = False,
):
    """PostgreSQL (pgvector) CRUD CLI - global options applied to every subcommand."""
    global _fake_embeddings_enabled
    _fake_embeddings_enabled = fake_embeddings
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
        logger.setLevel(logging.DEBUG)


def _resource_openai_v1_endpoint() -> str:
    """Strip the project segment off ``AZURE_AI_PROJECT_ENDPOINT``.

    Microsoft Foundry's project-scoped path does not currently serve the
    embeddings API; the resource-level path ``/openai/v1`` is required.
    Matches the helper in ``scripts/microsoft_foundry/vanilla.py``.
    """
    project_endpoint = get_microsoft_foundry_settings().azure_ai_project_endpoint
    resource = project_endpoint.split("/api/projects/", 1)[0]
    return f"{resource}/openai/v1"


def _build_embeddings(model_name: str, vector_size: int) -> Embeddings:
    """Build the embedding model used by every subcommand."""
    if _fake_embeddings_enabled:
        from langchain_core.embeddings import DeterministicFakeEmbedding

        logger.info("Using DeterministicFakeEmbedding(size=%d) (no Azure call)", vector_size)
        return DeterministicFakeEmbedding(size=vector_size)

    from langchain.embeddings import init_embeddings

    logger.info("Using Microsoft Foundry embedding model: azure_ai:%s", model_name)
    return init_embeddings(
        f"azure_ai:{model_name}",
        endpoint=_resource_openai_v1_endpoint(),
        credential=DefaultAzureCredential(),
        api_version="preview",
    )


@lru_cache(maxsize=1)
def _get_engine():
    """Return (and cache) a ``PGEngine`` connected to the local postgres service."""
    from langchain_postgres import PGEngine

    settings = get_postgres_settings()
    url = settings.connection_string
    logger.debug("Connecting to %s", url)
    return PGEngine.from_connection_string(url=url)


def _get_store(table_name: str, model_name: str, vector_size: int):
    """Build a ``PGVectorStore`` instance bound to the given table."""
    from langchain_postgres import PGVectorStore

    engine = _get_engine()
    embeddings = _build_embeddings(model_name=model_name, vector_size=vector_size)
    return PGVectorStore.create_sync(
        engine=engine,
        table_name=table_name,
        embedding_service=embeddings,
    )


@app.command(name="create-table", help="DDL: create the pgvector table used by the vector store")
def create_table(
    table_name: Annotated[
        str,
        typer.Option("--table", "-t", help="Table name to create"),
    ] = DEFAULT_SETTINGS["table_name"],
    vector_size: Annotated[
        int,
        typer.Option("--vector-size", "-d", help="Embedding vector dimension"),
    ] = DEFAULT_SETTINGS["vector_size"],
    overwrite: Annotated[
        bool,
        typer.Option(
            "--overwrite",
            help="Drop the table first if it already exists",
        ),
    ] = False,
):
    """Create the pgvector-backed table that holds documents and embeddings."""
    from langchain_postgres import Column

    engine = _get_engine()
    engine.init_vectorstore_table(
        table_name=table_name,
        vector_size=vector_size,
        id_column=Column("langchain_id", "TEXT", nullable=False),
        overwrite_existing=overwrite,
    )
    print(f"[create-table] table '{table_name}' ready (vector_size={vector_size}, overwrite={overwrite})")


@app.command(name="drop-table", help="DDL: drop the pgvector table")
def drop_table(
    table_name: Annotated[
        str,
        typer.Option("--table", "-t", help="Table name to drop"),
    ] = DEFAULT_SETTINGS["table_name"],
):
    """Drop the pgvector-backed table created by ``create-table``."""
    engine = _get_engine()
    engine.drop_table(table_name=table_name)
    print(f"[drop-table] table '{table_name}' dropped")


@app.command(name="create", help="CRUD/Create: insert a single document with optional id and metadata")
def create(
    text: Annotated[
        str,
        typer.Option("--text", "-x", help="Document text to embed and store"),
    ],
    doc_id: Annotated[
        str | None,
        typer.Option("--id", "-i", help="Document id (defaults to a generated UUID)"),
    ] = None,
    source: Annotated[
        str | None,
        typer.Option("--source", "-s", help="Optional ``source`` metadata field"),
    ] = None,
    table_name: Annotated[
        str,
        typer.Option("--table", "-t", help="Table name to write to"),
    ] = DEFAULT_SETTINGS["table_name"],
    model_name: Annotated[
        str,
        typer.Option("--model", "-m", help="Embedding model to use"),
    ] = DEFAULT_SETTINGS["embedding_model"],
    vector_size: Annotated[
        int,
        typer.Option("--vector-size", "-d", help="Embedding vector dimension"),
    ] = DEFAULT_SETTINGS["vector_size"],
):
    """Create a single document in the vector store."""
    store = _get_store(table_name=table_name, model_name=model_name, vector_size=vector_size)
    resolved_id = doc_id or str(uuid.uuid4())
    metadata: dict[str, str] = {}
    if source is not None:
        metadata["source"] = source
    store.add_documents(
        documents=[Document(page_content=text, metadata=metadata)],
        ids=[resolved_id],
    )
    print(f"[create] id={resolved_id} text={text!r} metadata={metadata}")


@app.command(name="bulk-create", help="CRUD/Create (bulk): insert a small batch of sample documents")
def bulk_create(
    table_name: Annotated[
        str,
        typer.Option("--table", "-t", help="Table name to write to"),
    ] = DEFAULT_SETTINGS["table_name"],
    model_name: Annotated[
        str,
        typer.Option("--model", "-m", help="Embedding model to use"),
    ] = DEFAULT_SETTINGS["embedding_model"],
    vector_size: Annotated[
        int,
        typer.Option("--vector-size", "-d", help="Embedding vector dimension"),
    ] = DEFAULT_SETTINGS["vector_size"],
):
    """Insert a tiny built-in document set so ``search`` returns something useful."""
    samples = [
        Document(id="apple", page_content="Apples and oranges are fruits.", metadata={"source": "seed"}),
        Document(id="car", page_content="Cars and airplanes are vehicles.", metadata={"source": "seed"}),
        Document(id="train", page_content="A train runs on rails.", metadata={"source": "seed"}),
        Document(id="dog", page_content="Dogs and cats are common pets.", metadata={"source": "seed"}),
    ]
    store = _get_store(table_name=table_name, model_name=model_name, vector_size=vector_size)
    ids = [doc.id for doc in samples if doc.id is not None]
    store.add_documents(documents=samples, ids=ids)
    print(f"[bulk-create] inserted {len(samples)} sample documents into '{table_name}'")
    for doc in samples:
        print(f"  - id={doc.id} text={doc.page_content!r}")


@app.command(name="read", help="CRUD/Read: fetch documents by id")
def read(
    ids: Annotated[
        list[str],
        typer.Option("--id", "-i", help="Document id(s) to fetch (repeatable)"),
    ],
    table_name: Annotated[
        str,
        typer.Option("--table", "-t", help="Table name to read from"),
    ] = DEFAULT_SETTINGS["table_name"],
    model_name: Annotated[
        str,
        typer.Option("--model", "-m", help="Embedding model to use"),
    ] = DEFAULT_SETTINGS["embedding_model"],
    vector_size: Annotated[
        int,
        typer.Option("--vector-size", "-d", help="Embedding vector dimension"),
    ] = DEFAULT_SETTINGS["vector_size"],
):
    """Read one or more documents by their id."""
    store = _get_store(table_name=table_name, model_name=model_name, vector_size=vector_size)
    documents = store.get_by_ids(ids)
    if not documents:
        print(f"[read] no documents found for ids={ids}")
        return
    for doc in documents:
        print(f"  - id={doc.id} text={doc.page_content!r} metadata={doc.metadata}")


@app.command(name="search", help="CRUD/Read (semantic): run a similarity search against the vector store")
def search(
    query: Annotated[
        str,
        typer.Option("--query", "-q", help="Query text to embed and search for"),
    ],
    k: Annotated[
        int,
        typer.Option("--k", "-k", help="Number of similar documents to return"),
    ] = 3,
    table_name: Annotated[
        str,
        typer.Option("--table", "-t", help="Table name to read from"),
    ] = DEFAULT_SETTINGS["table_name"],
    model_name: Annotated[
        str,
        typer.Option("--model", "-m", help="Embedding model to use"),
    ] = DEFAULT_SETTINGS["embedding_model"],
    vector_size: Annotated[
        int,
        typer.Option("--vector-size", "-d", help="Embedding vector dimension"),
    ] = DEFAULT_SETTINGS["vector_size"],
):
    """Similarity search: return the top-k documents closest to ``--query``."""
    store = _get_store(table_name=table_name, model_name=model_name, vector_size=vector_size)
    results = store.similarity_search(query=query, k=k)
    print(f"[search] query={query!r} k={k}")
    if not results:
        print("  (no matches)")
        return
    for doc in results:
        print(f"  - id={doc.id} text={doc.page_content!r} metadata={doc.metadata}")


@app.command(name="update", help="CRUD/Update: replace a document's text and metadata by id")
def update(
    doc_id: Annotated[
        str,
        typer.Option("--id", "-i", help="Document id to update"),
    ],
    text: Annotated[
        str,
        typer.Option("--text", "-x", help="New document text"),
    ],
    source: Annotated[
        str | None,
        typer.Option("--source", "-s", help="Optional ``source`` metadata override"),
    ] = None,
    table_name: Annotated[
        str,
        typer.Option("--table", "-t", help="Table name to write to"),
    ] = DEFAULT_SETTINGS["table_name"],
    model_name: Annotated[
        str,
        typer.Option("--model", "-m", help="Embedding model to use"),
    ] = DEFAULT_SETTINGS["embedding_model"],
    vector_size: Annotated[
        int,
        typer.Option("--vector-size", "-d", help="Embedding vector dimension"),
    ] = DEFAULT_SETTINGS["vector_size"],
):
    """Update is implemented as ``delete + add`` for the same id, so embeddings are refreshed."""
    store = _get_store(table_name=table_name, model_name=model_name, vector_size=vector_size)
    store.delete(ids=[doc_id])
    metadata: dict[str, str] = {}
    if source is not None:
        metadata["source"] = source
    store.add_documents(
        documents=[Document(page_content=text, metadata=metadata)],
        ids=[doc_id],
    )
    print(f"[update] id={doc_id} text={text!r} metadata={metadata}")


@app.command(name="delete", help="CRUD/Delete: remove one or more documents by id")
def delete(
    ids: Annotated[
        list[str],
        typer.Option("--id", "-i", help="Document id(s) to delete (repeatable)"),
    ],
    table_name: Annotated[
        str,
        typer.Option("--table", "-t", help="Table name to delete from"),
    ] = DEFAULT_SETTINGS["table_name"],
    model_name: Annotated[
        str,
        typer.Option("--model", "-m", help="Embedding model to use"),
    ] = DEFAULT_SETTINGS["embedding_model"],
    vector_size: Annotated[
        int,
        typer.Option("--vector-size", "-d", help="Embedding vector dimension"),
    ] = DEFAULT_SETTINGS["vector_size"],
):
    """Delete one or more documents by id."""
    store = _get_store(table_name=table_name, model_name=model_name, vector_size=vector_size)
    store.delete(ids=ids)
    print(f"[delete] deleted ids={ids}")


if __name__ == "__main__":
    if not load_dotenv(override=True, verbose=True):
        logging.warning("No .env file found; using defaults")
    app()
