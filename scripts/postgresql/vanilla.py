"""Unified CRUD CLI for the local pgvector and Azure Database for PostgreSQL.

This script merges the previous ``scripts/postgresql/crud.py`` (local Docker
Compose pgvector) and ``scripts/postgresql/crud_azure.py`` (managed Azure
Database for PostgreSQL Flexible Server) into a single Typer CLI. The only
runtime difference between the two targets is the connection string and how
the database password is resolved, so we keep the target-specific logic
isolated in :func:`_build_connection_url` and share everything else
(embeddings, table DDL, CRUD subcommands).

Pick the target with the global ``--target/-T`` option (``docker`` or
``azure``).

Local pgvector (Docker Compose) usage::

    # Start the local PostgreSQL service first
    docker compose up -d postgres

    # Defaults to --target docker
    uv run python scripts/postgresql/vanilla.py create-table
    uv run python scripts/postgresql/vanilla.py bulk-create
    uv run python scripts/postgresql/vanilla.py search --query "fruit"
    uv run python scripts/postgresql/vanilla.py drop-table

Azure Database for PostgreSQL Flexible Server usage::

    # Authenticate the local environment with Azure (Entra) if needed
    az login

    uv run python scripts/postgresql/vanilla.py --target azure create-table
    uv run python scripts/postgresql/vanilla.py --target azure bulk-create
    uv run python scripts/postgresql/vanilla.py --target azure search --query "fruit"
    uv run python scripts/postgresql/vanilla.py --target azure drop-table

The defaults align with the embedding deployment used by
``scripts/microsoft_foundry/vanilla.py`` (``text-embedding-3-small`` returning
1536-dimensional vectors). Override with ``--vector-size`` if you switch to
a model with a different dimension (for example ``text-embedding-3-large``
returns 3072).

Notes on the Azure target
-------------------------
The Azure target follows the authentication pattern documented in the
Microsoft Learn guide
[Use LangChain with Azure Database for PostgreSQL](https://learn.microsoft.com/en-us/azure/postgresql/azure-ai/generative-ai-develop-with-langchain).
We deliberately reuse ``langchain-postgres`` (instead of
``langchain-azure-postgresql`` / ``AzurePGVectorStore``) because at the time
of writing the Azure package pins ``pgvector>=0.4,<0.5`` while
``langchain-postgres==0.0.17`` pins ``pgvector>=0.2.5,<0.4``, so the two
cannot coexist. Azure Database for PostgreSQL Flexible Server is plain
PostgreSQL with the ``vector`` extension, so a single ``langchain-postgres``
client and an Azure-aware connection string (SSL required, optional Entra
access token used as the database password) cover both targets.

Prerequisites for the Azure target:

- ``pgvector`` enabled on the Azure server
  (https://learn.microsoft.com/en-us/azure/postgresql/extensions/how-to-use-pgvector).
- A PostgreSQL role for either password or Microsoft Entra authentication.
- Environment variables described in ``.env.template`` (``AZURE_DBHOST``,
  ``AZURE_DBNAME``, ``AZURE_DBUSER``, ``AZURE_DBPASSWORD``, ``AZURE_SSLMODE``,
  ``AZURE_USE_ENTRA_AUTH``).
"""

import logging
import uuid
from enum import Enum
from functools import lru_cache
from typing import Annotated

import typer
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from concierge.loggers import get_logger
from concierge.settings import (
    get_azure_postgres_settings,
    get_microsoft_foundry_settings,
    get_postgres_settings,
)


class Target(str, Enum):
    """Which PostgreSQL deployment the CLI should talk to."""

    docker = "docker"
    azure = "azure"


DEFAULT_SETTINGS = {
    "embedding_model": "text-embedding-3-small",
    # ``text-embedding-3-small`` returns 1536-dimensional vectors. Override
    # with ``--vector-size`` if you switch to a model that uses a different
    # dimension (for example, ``text-embedding-3-large`` returns 3072).
    "vector_size": 1536,
    "table_name": "concierge_docs",
}

app = typer.Typer(
    add_completion=False,
    help=(
        "PostgreSQL (pgvector) CRUD CLI for the LangChain vector store. "
        "Use --target/-T to switch between the local Docker Compose service "
        "and an Azure Database for PostgreSQL Flexible Server."
    ),
)

logger = get_logger(__name__)

# Module-level state set by the global options below. Each Typer invocation
# touches only one target, so plain module-level variables are enough.
_fake_embeddings_enabled: bool = False
_target: Target = Target.docker


@app.callback()
def _global_options(
    target: Annotated[
        Target,
        typer.Option(
            "--target",
            "-T",
            help=(
                "PostgreSQL deployment to talk to. ``docker`` uses the local "
                "compose service (see ``compose.yml``). ``azure`` uses an Azure "
                "Database for PostgreSQL Flexible Server (see ``.env.template`` "
                "for the required ``AZURE_*`` variables)."
            ),
            case_sensitive=False,
        ),
    ] = Target.docker,
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
                "Handy for purely-local testing (with ``--target docker``) or for "
                "exercising the Azure connection path (with ``--target azure``) "
                "without having to call out to an embedding deployment."
            ),
        ),
    ] = False,
):
    """Global options applied to every subcommand."""
    global _fake_embeddings_enabled, _target
    _fake_embeddings_enabled = fake_embeddings
    _target = target
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


# ---------------------------------------------------------------------------
# Target-specific logic is localised here. Everything below this section is
# shared between the docker and azure targets.
# ---------------------------------------------------------------------------


def _resolve_azure_credentials() -> tuple[str, str]:
    """Return ``(user, password)`` for the Azure PostgreSQL connection.

    With ``AZURE_USE_ENTRA_AUTH=true`` we exchange the local Entra credentials
    for an access token scoped to ``ossrdbms-aad.database.windows.net`` and
    use that token as the database password. Otherwise we use
    ``AZURE_DBUSER`` and ``AZURE_DBPASSWORD`` verbatim.
    """
    settings = get_azure_postgres_settings()
    if settings.use_entra_auth:
        logger.info("Acquiring Microsoft Entra access token for Azure PostgreSQL")
        token = DefaultAzureCredential().get_token(settings.entra_token_scope)
        if not settings.dbuser:
            raise typer.BadParameter(
                "AZURE_DBUSER must be set to the Entra principal name (or PostgreSQL "
                "role mapped to that principal) when AZURE_USE_ENTRA_AUTH=true.",
            )
        return settings.dbuser, token.token
    if not (settings.dbuser and settings.dbpassword):
        raise typer.BadParameter(
            "AZURE_DBUSER and AZURE_DBPASSWORD must be set when AZURE_USE_ENTRA_AUTH=false.",
        )
    return settings.dbuser, settings.dbpassword


def _build_connection_url(target: Target) -> str:
    """Return the ``postgresql+psycopg://...`` URL for the chosen target.

    This is the single place where the two deployments differ. Add a new
    branch here (and update the ``Target`` enum) to support another target.
    """
    if target is Target.docker:
        settings = get_postgres_settings()
        url = settings.connection_string
        logger.debug("Connecting to %s", url)
        return url

    # Azure Database for PostgreSQL Flexible Server.
    azure_settings = get_azure_postgres_settings()
    if not azure_settings.dbhost or not azure_settings.dbname:
        raise typer.BadParameter(
            "AZURE_DBHOST and AZURE_DBNAME must be set in the environment (.env). "
            "See .env.template for the required Azure PostgreSQL variables.",
        )
    user, password = _resolve_azure_credentials()
    url = azure_settings.build_connection_string(password=password, user=user)
    # Avoid logging the token / password in the connection string.
    logger.debug(
        "Connecting to postgresql+psycopg://%s@%s:%d/%s?sslmode=%s",
        user,
        azure_settings.dbhost,
        azure_settings.dbport,
        azure_settings.dbname,
        azure_settings.sslmode,
    )
    return url


# ---------------------------------------------------------------------------
# Shared engine/store helpers and CRUD subcommands.
# ---------------------------------------------------------------------------


@lru_cache(maxsize=len(Target))
def _get_engine(target: Target):
    """Return (and cache) a ``PGEngine`` connected to the chosen target."""
    from langchain_postgres import PGEngine

    url = _build_connection_url(target)
    return PGEngine.from_connection_string(url=url)


def _get_store(table_name: str, model_name: str, vector_size: int):
    """Build a ``PGVectorStore`` instance bound to the given table."""
    from langchain_postgres import PGVectorStore

    engine = _get_engine(_target)
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

    engine = _get_engine(_target)
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
    engine = _get_engine(_target)
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
