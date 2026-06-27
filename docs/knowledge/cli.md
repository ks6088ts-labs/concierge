---
title: Knowledge CLI Reference
description: Typer CLI for ingesting Markdown into the pgvector-backed knowledge store
---

## Installation

`knowledge-cli` is installed automatically by `uv sync` and registered in
`pyproject.toml` under `[project.scripts]`.

```bash
uv run knowledge-cli --help
```

The CLI exposes two subcommand groups:

* `ingest` — write side: `run`, `stats`, `drop`.
* `search` — read side: `run`.

## Global observability options

These flags are processed by the top-level callback, so they must be passed
**before** the subcommand name:

| Flag | Short | Description |
|------|-------|-------------|
| `--tracing` | `-t` | Enable shared tracing state (`concierge` tracer). |
| `--mlflow`  | `-m` | Enable `mlflow.langchain.autolog()` bootstrap. |
| `--verbose` | `-v` | Enable DEBUG logging. |

Example:

```bash
uv run knowledge-cli -t -v -m ingest run --collection demo_md docs
```

`.env` is loaded automatically via `load_dotenv()` on every invocation.

!!! note "MLflow trace grouping"
    When `--mlflow` is enabled, `ingest run` wraps the entire ingest in an
    MLflow parent span (`knowledge.ingest.run`) so that per-chunk
    embedding HTTP calls captured by `mlflow.openai.autolog()` are nested
    under one trace per CLI invocation instead of appearing as separate
    root traces in the MLflow UI.

## Commands

### `ingest run` — index Markdown files

```bash
uv run knowledge-cli ingest run [OPTIONS] PATHS...
```

Recursively collects every `*.md` file under each `PATHS` entry (files are
accepted too), splits them with `RecursiveCharacterTextSplitter`
(`KNOWLEDGE_CHUNK_SIZE` / `KNOWLEDGE_CHUNK_OVERLAP`), embeds each chunk, and
upserts them into the target pgvector table. The table is created
automatically when it does not exist.

| Flag | Default | Description |
|------|---------|-------------|
| `--collection` | `KNOWLEDGE_DEFAULT_COLLECTION` | Table name. Must match `^[A-Za-z0-9_]+$`. |
| `--target` | `docker` | `docker` (`POSTGRES_*`) or `azure` (`AZURE_*`). Case-insensitive. |

Successful output:

```
ingest completed: files=<N> chunks=<M> records=<M>
```

`records` is the total row count in the collection after the upsert (not
the number of rows inserted this run), so re-running `ingest run` against
the same content will keep `records` stable thanks to the deterministic
`ChunkId` (`{collection}:{source}:{chunk_index}:{sha256[:12]}`).

### `ingest stats` — show collection size

```bash
uv run knowledge-cli ingest stats [--collection NAME] [--target docker|azure]
```

Returns the current number of rows. Missing tables are reported as `0`
rather than raising, so it is safe to run before the first ingest.

```
collection=demo_md records=42
```

### `ingest drop` — delete a collection

```bash
uv run knowledge-cli ingest drop [--collection NAME] [--target docker|azure] [--yes]
```

Drops the pgvector table via `PGEngine.drop_table`. By default a
confirmation prompt is shown; pass `--yes` / `-y` to skip it (for CI).

```
dropped collection=demo_md
```

### `search run` — query a collection

```bash
uv run knowledge-cli search run [OPTIONS] QUERY
```

Embeds `QUERY` with the same `create_embeddings()` factory used at
ingest time and runs a `similarity_search` against the target pgvector
collection. The collection table must already exist (`ingest run` is
the only command that creates one).

| Flag | Default | Description |
|------|---------|-------------|
| `--collection` | `KNOWLEDGE_DEFAULT_COLLECTION` | Table to search. Must match `^[A-Za-z0-9_]+$`. |
| `--target` | `docker` | `docker` (`POSTGRES_*`) or `azure` (`AZURE_*`). Case-insensitive. |
| `--k` / `-k` | `4` | Number of results to return (must be `>= 1`). |
| `--snippet` | `200` | Max characters of each chunk to print. `0` prints the full chunk. Truncated content is suffixed with `...`. |
| `--json` | _(off)_ | Emit a raw JSON array of `{id, content, metadata}` instead of human-readable text. Useful for piping into other tools. |

Human-readable output:

```
collection=demo_md query='vector store' hits=2
[1] source=docs/tutorial/03-postgres-vector-store.md chunk=0
pgvector is a PostgreSQL extension that lets you store and query...
[2] source=docs/knowledge/index.md chunk=2
`concierge.knowledge` is a standalone bounded context...
```

JSON output (`--json`):

```json
[
  {
    "id": "demo_md:docs/tutorial/03-postgres-vector-store.md:0:abc123def456",
    "content": "pgvector is a PostgreSQL extension...",
    "metadata": {
      "source": "docs/tutorial/03-postgres-vector-store.md",
      "collection": "demo_md",
      "chunk_index": 0,
      "content_sha256": "...",
      "ingested_at": "2026-05-24T12:34:56+00:00"
    }
  }
]
```

When no chunks match the query, the command exits with code `0` and
prints:

```
no results for collection=demo_md query='nothing matches'
```

## Environment variables

See the [Knowledge Indexer overview](index.md#configuration) for the
complete table. The most useful ones during smoke tests:

| Variable | Smoke-test value | Notes |
|----------|------------------|-------|
| `KNOWLEDGE_EMBEDDING_PROVIDER` | `fake` | No Foundry call, deterministic vectors. |
| `KNOWLEDGE_DEFAULT_COLLECTION` | `demo_md` | Lets you drop `--collection` from every command. |
| `KNOWLEDGE_CHUNK_SIZE` / `KNOWLEDGE_CHUNK_OVERLAP` | `1000` / `200` | Defaults are reasonable for English / Japanese prose. |
| `AZURE_AI_PROJECT_ENDPOINT` | – | Required when `KNOWLEDGE_EMBEDDING_PROVIDER=foundry`. |

!!! warning "`fake` is plumbing-only — switch to `foundry` for real search"
    `fake` embeddings (`DeterministicFakeEmbedding`) are semantically
    meaningless, so a collection built with `fake` returns irrelevant search
    results (and RAG/realtime callers report "no relevant results"). For real
    retrieval set `KNOWLEDGE_EMBEDDING_PROVIDER=foundry` and **re-ingest**
    (`ingest drop` then `ingest run`) — see
    [Troubleshooting](index.md#troubleshooting).

## Minimum end-to-end procedure

The shortest path from a fresh checkout to a populated and verifiable
collection:

```bash
# 1. Boot pgvector and use fake embeddings (no Azure required)
docker compose up -d postgres
export KNOWLEDGE_EMBEDDING_PROVIDER=fake

# 2. Ingest this repository's docs/ directory
uv run knowledge-cli ingest run --collection demo_md docs

# 3. Verify the row count
uv run knowledge-cli ingest stats --collection demo_md

# 4. (Optional) tear down
uv run knowledge-cli ingest drop --collection demo_md --yes
```

For the Azure variant, swap step 1 for `az login` plus the `AZURE_*`
environment block from
[Step 3 – PostgreSQL (pgvector) CRUD](../tutorial/03-postgres-vector-store.md),
and add `--target azure` to every command.
