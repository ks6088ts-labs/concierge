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

!!! tip "Running against Azure end to end"

    For a full Azure setup (Foundry endpoints, Azure Database for PostgreSQL, and schema initialization), follow [Appendix - Azure Environment Setup](tutorial/appendix-azure-environment-setup.md).

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

The same global options are available on service CLIs as well:

```bash
uv run chat-cli --tracing --mlflow --help
uv run cloud-agent-cli --tracing --mlflow --help
uv run todo-cli --tracing --mlflow --help
```

Start a local MLflow UI in a separate terminal when using `--mlflow`.

```bash
make mlflow
```

Forward VS Code GitHub Copilot Chat OpenTelemetry signals to Azure
Application Insights via the bundled OTel collector (opt-in; requires
`APPLICATIONINSIGHTS_CONNECTION_STRING` in `.env`):

```bash
make copilot-otel-up    # start the docker-compose otel-collector service
make copilot-otel-logs  # tail collector logs
make copilot-otel-down  # stop the collector
```

Full setup (VS Code `settings.json`, KQL verification, troubleshooting) is in
[Monitor VS Code Copilot via App Insights](tutorial/appendix-monitor-vscode-copilot.md).

## Development Commands

Use Makefile targets for common operations.

```bash
# Show available make targets.
make

# Run tests.
make test

# Run format check, lint, and tests.
make ci-test

# Enforce clean architecture dependency direction with import-linter.
make lint-imports

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

A single Typer CLI in
[`scripts/postgresql/vanilla.py`](https://github.com/ks6088ts-labs/concierge/blob/main/scripts/postgresql/vanilla.py)
covers both targets supported by this repo:

* `--target docker` (default) talks to the local
  [pgvector](https://github.com/pgvector/pgvector) PostgreSQL service from
  [`compose.yml`](https://github.com/ks6088ts-labs/concierge/blob/main/compose.yml).
* `--target azure` talks to a managed
  [Azure Database for PostgreSQL Flexible Server](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/overview)
  with `pgvector` enabled, defaulting to Microsoft Entra authentication
  (an access token from `DefaultAzureCredential` is used as the database
  password).

See [Step 3 - PostgreSQL (pgvector) CRUD](tutorial/03-postgres-vector-store.md)
for the full walkthrough (including server provisioning and Entra setup
for the Azure target).

### Configure the connection

Both targets read settings from `.env`. Copy the relevant block(s) from
[`.env.template`](https://github.com/ks6088ts-labs/concierge/blob/main/.env.template):

```dotenv
# --target docker (defaults match the `postgres` service in compose.yml)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=concierge
POSTGRES_PASSWORD=concierge
POSTGRES_DB=concierge
POSTGRES_COLLECTION=concierge_docs

# --target azure
AZURE_DBHOST=<server-name>.postgres.database.azure.com
AZURE_DBNAME=postgres
AZURE_DBPORT=5432
AZURE_SSLMODE=require
# Use Microsoft Entra ID (recommended) - AZURE_DBUSER must be the principal name.
AZURE_USE_ENTRA_AUTH=true
AZURE_DBUSER=<entra-principal-or-db-user>
# Only required when AZURE_USE_ENTRA_AUTH=false.
AZURE_DBPASSWORD=
```

### Start (or sign in to) the target service

For the local target, start the Compose service:

```bash
docker compose up -d postgres
```

For the Azure target, sign in so `DefaultAzureCredential` can pick up your
identity:

```bash
az login
```

### Run the CRUD CLI

The subcommand surface is identical for both targets - swap
`--target docker` for `--target azure` to switch.

```bash
# List available Typer subcommands.
uv run python scripts/postgresql/vanilla.py --help

# Create the pgvector table, bulk-insert sample documents, and search.
uv run python scripts/postgresql/vanilla.py create-table
uv run python scripts/postgresql/vanilla.py bulk-create
uv run python scripts/postgresql/vanilla.py search --query "fruit"

# Same flow against the Azure Flexible Server.
uv run python scripts/postgresql/vanilla.py --target azure create-table
uv run python scripts/postgresql/vanilla.py --target azure bulk-create
uv run python scripts/postgresql/vanilla.py --target azure search --query "fruit"

# Read, update, delete by id.
uv run python scripts/postgresql/vanilla.py read --id apple
uv run python scripts/postgresql/vanilla.py update --id apple \
    --text "Apples, oranges, and bananas are fruits."
uv run python scripts/postgresql/vanilla.py delete --id apple

# Drop the table when you are done.
uv run python scripts/postgresql/vanilla.py drop-table
```

Use `--fake-embeddings` to skip Microsoft Foundry and run end-to-end against
`DeterministicFakeEmbedding`. This works for both targets - it is handy for
purely-local iteration with `--target docker`, and also for exercising the
Azure connection path with `--target azure` before a Foundry embedding
deployment is ready.

```bash
uv run python scripts/postgresql/vanilla.py --fake-embeddings create-table --overwrite
uv run python scripts/postgresql/vanilla.py --fake-embeddings bulk-create
uv run python scripts/postgresql/vanilla.py --fake-embeddings search \
    --query "fruit"

# Same flag against the Azure target.
uv run python scripts/postgresql/vanilla.py --target azure --fake-embeddings create-table --overwrite
```

### Inspect or stop the local database

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
