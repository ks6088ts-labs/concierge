---
title: Development Guide
description: Local setup, CLI examples, documentation commands, and Docker commands for concierge
---

## Local Setup

Install development dependencies and copy the environment template.

```bash
make install-deps-dev
cp .env.template .env
```

Set your Microsoft Foundry project endpoint in `.env`.

```dotenv
AZURE_AI_PROJECT_ENDPOINT=https://<resource>.services.ai.azure.com/api/projects/<project>
MLFLOW_TRACKING_URI=http://127.0.0.1:5000
```

Sign in with Azure CLI before connecting to Foundry.

```bash
az login
```

## Sample CLI

List available Typer commands.

```bash
uv run python scripts/microsoft_foundry/vanilla.py --help
```

Run representative examples.

```bash
uv run python scripts/microsoft_foundry/vanilla.py hello-world \
    --query "Summarize LangChain in one sentence."

uv run python scripts/microsoft_foundry/vanilla.py use-in-agents \
    --query "Explain why observability matters for LLM applications."

uv run python scripts/microsoft_foundry/vanilla.py vector-store-search \
    --query thud --k 1
```

Use global options to enable observability.

* `--tracing` sends LangChain runs to Microsoft Foundry / Azure Monitor tracing.
* `--mlflow` enables MLflow LangChain autologging.
* `--verbose` sets the local logger to `DEBUG`.

Start a local MLflow UI in a separate terminal when using `--mlflow`.

```bash
make mlflow
```

## Development Commands

Use Makefile targets for common operations.

```bash
# Show available make targets.
make

# Run tests.
make test

# Run format check, lint, and tests.
make ci-test

# Install docs dependencies and build the site.
make ci-test-docs

# Build documentation.
make docs

# Preview documentation locally.
make docs-serve
```

Build and run the Docker image through Makefile targets.

```bash
make docker-build
make docker-run
```

## PostgreSQL (pgvector) CRUD

The [`compose.yml`](https://github.com/ks6088ts-labs/concierge/blob/main/compose.yml)
file ships a [pgvector](https://github.com/pgvector/pgvector) PostgreSQL service
that can host a LangChain `PGVectorStore`. Start it with Docker Compose.

```bash
docker compose up -d postgres
```

Defaults from [`.env.template`](https://github.com/ks6088ts-labs/concierge/blob/main/.env.template):

```dotenv
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=concierge
POSTGRES_PASSWORD=concierge
POSTGRES_DB=concierge
POSTGRES_COLLECTION=concierge_docs
```

Run the CRUD CLI defined in
[`scripts/postgresql/crud.py`](https://github.com/ks6088ts-labs/concierge/blob/main/scripts/postgresql/crud.py).

```bash
# List available Typer subcommands.
uv run python scripts/postgresql/crud.py --help

# Create the pgvector table, bulk-insert sample documents, and search.
uv run python scripts/postgresql/crud.py create-table
uv run python scripts/postgresql/crud.py bulk-create
uv run python scripts/postgresql/crud.py search --query "fruit"

# Read, update, delete by id.
uv run python scripts/postgresql/crud.py read --id apple
uv run python scripts/postgresql/crud.py update --id apple \
    --text "Apples, oranges, and bananas are fruits."
uv run python scripts/postgresql/crud.py delete --id apple

# Drop the table when you are done.
uv run python scripts/postgresql/crud.py drop-table
```

Use `--fake-embeddings` to skip Microsoft Foundry and run end-to-end against
`DeterministicFakeEmbedding`, which is helpful when iterating locally without
Azure credentials.

```bash
uv run python scripts/postgresql/crud.py --fake-embeddings create-table
uv run python scripts/postgresql/crud.py --fake-embeddings bulk-create
uv run python scripts/postgresql/crud.py --fake-embeddings search \
    --query "fruit"
```

Stop or inspect the database with `docker compose` directly.

```bash
# Tail PostgreSQL logs.
docker compose logs -f postgres

# Open a psql shell inside the container.
docker compose exec postgres psql -U concierge -d concierge

# Stop and remove the service (volume is preserved).
docker compose stop postgres
docker compose rm -f postgres
```

## GitHub Pages

The [github-pages workflow](https://github.com/ks6088ts-labs/concierge/actions/workflows/github-pages.yaml) deploys the MkDocs site from `main` with `mkdocs gh-deploy --force`.

* [Published documentation](https://ks6088ts-labs.github.io/concierge/)
* [Japanese documentation](https://ks6088ts-labs.github.io/concierge/ja/)
* [Hands-on tutorial](https://ks6088ts-labs.github.io/concierge/tutorial/)
