---
title: Appendix - Azure Environment Setup
description: End-to-end setup for running concierge against Azure, covering Foundry endpoints, Azure Database for PostgreSQL, and schema initialization
---

## Azure Environment Setup

This appendix takes you from a fresh clone to a running concierge backed by Azure: Foundry model endpoints for the LLM, realtime, and image features, plus Azure Database for PostgreSQL for persistence. Follow the steps in order.

!!! note

    For local-only development with Docker pgvector and no Azure dependency, follow the [Development Guide](../development.md) and tutorial steps 1 through 3 instead. This appendix covers the managed Azure path.

### What you will configure

* Foundry project endpoints for chat/LLM, realtime voice, and image generation
* Azure Database for PostgreSQL connection with Microsoft Entra authentication
* Persistence backends for the Todo, Chat, and Cloud Agent apps
* Optional knowledge search over Azure PostgreSQL and a durable Cloud Agent queue

### Prerequisites

Install dependencies, copy the environment template, and sign in.

```bash
make install-deps-dev
cp .env.template .env
az login
```

You also need the following in your subscription:

* One or more Azure AI Foundry (AIServices) resources, each with the model deployments you intend to use.
* An Azure Database for PostgreSQL Flexible Server with the `pgvector` extension available.
* A Storage account, only if you plan to use the durable Cloud Agent queue.

Required access:

* The "Azure AI Developer" role on each Foundry project you reference.
* A Microsoft Entra principal that PostgreSQL recognizes (the server Entra admin, or a role mapped to your principal).
* The "Storage Queue Data Contributor" role on the Storage account when you enable the queue.

### Step 1: Discover your resources

Run these read-only commands and keep the output nearby. You will paste values from here into `.env` in Step 3.

```bash
# Current subscription and signed-in user
az account show --query "{name:name, id:id, user:user.name}" -o json

# Foundry (AIServices) accounts
az cognitiveservices account list \
  --query "[].{name:name, kind:kind, location:location, rg:resourceGroup}" -o table

# Model deployments for one account (repeat for each account)
az cognitiveservices account deployment list -g <rg> -n <account> \
  --query "[].{name:name, model:properties.model.name}" -o table

# Foundry project name (used in the endpoint path)
az rest --method get \
  --url "https://management.azure.com/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<account>/projects?api-version=2025-04-01-preview" \
  --query "value[].name" -o json

# PostgreSQL Flexible Server
az postgres flexible-server list \
  --query "[].{name:name, fqdn:fullyQualifiedDomainName, rg:resourceGroup, version:version}" -o table

# PostgreSQL Microsoft Entra admin (who can sign in with a token)
az postgres flexible-server microsoft-entra-admin list -g <rg> --server-name <server> \
  --query "[].principalName" -o json

# Storage account (optional, for the Cloud Agent queue)
az storage account list --query "[].{name:name, queue:primaryEndpoints.queue}" -o table
```

!!! tip

    A Foundry project endpoint always has the shape `https://<account>.services.ai.azure.com/api/projects/<project>`. The projects call returns `<account>/<project>`; the value after the slash is your `<project>`. On Azure CLI older than 2.86, the admin command is `ad-admin` rather than `microsoft-entra-admin`.

### Step 2: Map deployments to Foundry endpoints

Concierge can target up to three Foundry projects. Choose each one by the model deployment it hosts.

| Variable | Use the Foundry project that hosts |
|---|---|
| `AZURE_AI_PROJECT_ENDPOINT` | chat/LLM and embeddings (for example gpt-5, gpt-4o, text-embedding-3-small) |
| `AZURE_AI_PROJECT_ENDPOINT_REALTIME` | the realtime model (for example gpt-realtime-1.5), often in a different region |
| `AZURE_AI_PROJECT_ENDPOINT_IMAGE` | the image model (gpt-image-2), available in a limited set of regions |

!!! note

    A single Foundry resource can host all three. Separate endpoints exist only because realtime and image models are offered in fewer regions than the core chat models.

### Step 3: Fill in .env

Edit `.env` (copied from [.env.template](https://github.com/ks6088ts-labs/concierge/blob/main/.env.template)). The block below is the minimum for an Azure-backed run. Replace every `<...>` placeholder with a value from Step 1.

```dotenv
# --- Foundry endpoints (see Step 2) ---
AZURE_AI_PROJECT_ENDPOINT=https://<llm-account>.services.ai.azure.com/api/projects/<project>
AZURE_AI_PROJECT_ENDPOINT_REALTIME=https://<realtime-account>.services.ai.azure.com/api/projects/<project>
AZURE_AI_PROJECT_ENDPOINT_IMAGE=https://<image-account>.services.ai.azure.com/api/projects/<project>

# --- Azure Database for PostgreSQL (Microsoft Entra auth) ---
AZURE_DBHOST=<server-name>.postgres.database.azure.com
AZURE_DBNAME=appdb
AZURE_DBUSER=<entra-principal>
AZURE_USE_ENTRA_AUTH=true

# --- Use Azure PostgreSQL for every app's persistence ---
TODO_REPOSITORY_BACKEND=azure-postgres
CHAT_REPOSITORY_BACKEND=azure-postgres
CLOUD_AGENT_REPOSITORY_BACKEND=azure-postgres

# --- Chat replies via the streaming Foundry responder ---
CHAT_BOT_AGENT_TYPE=foundry
```

Add these only when you want the matching optional feature.

```dotenv
# Knowledge search tool over Azure PostgreSQL
AGENTS_KNOWLEDGE__TOOLS=search_docs
AGENTS_KNOWLEDGE__TARGET=azure
AGENTS_KNOWLEDGE__SEARCH_DOCS__COLLECTION=knowledge_default

# Durable Cloud Agent queue
CLOUD_AGENT_QUEUE_BACKEND=azure-storage-queue
CLOUD_AGENT_AZURE_STORAGE_ACCOUNT_URL=https://<account>.queue.core.windows.net
```

!!! warning "AZURE_DBUSER must be a recognized Entra principal"

    `AZURE_DBUSER` must be the Microsoft Entra principal that PostgreSQL recognizes. When it is the server Entra admin, it can create tables right away. For any other principal, create a matching database role and grant privileges first. The [PostgreSQL tutorial](03-postgres-vector-store.md) covers the Entra configuration.

!!! note "Responder and tool availability"

    `CHAT_RESPONDER_BACKEND` is deprecated and emits a warning; use `CHAT_BOT_AGENT_TYPE` only. The `foundry` responder streams replies but does not call agent tools, so the knowledge tool is unavailable in text chat under that responder. To use the knowledge tool in text chat, set `CHAT_BOT_AGENT_TYPE=langgraph`. Realtime voice includes the knowledge tool regardless of the responder.

### Step 4: Initialize the database schema

The SQL backends do not auto-migrate for the CLIs, so create the tables once per app.

```bash
uv run chat-cli db init     # chat_conversations, chat_participants, chat_messages
uv run todo-cli db init     # todo_tasks
```

The Cloud Agent web and worker create `cloud_agent_tasks` automatically on startup. To create it ahead of time:

```bash
uv run python -c "from dotenv import load_dotenv; load_dotenv(); from concierge.cloud_agent.infrastructure.persistence.factory import get_task_repository; get_task_repository()"
```

When you enabled the knowledge tool, populate its collection. The table is created on the first ingest.

```bash
uv run knowledge-cli ingest run ./docs --collection knowledge_default --target azure
```

All DDL uses `CREATE TABLE IF NOT EXISTS`, so re-running these commands is safe.

### Step 5: Verify

A successful, idempotent re-run confirms the schema exists. You can also start an app and exercise it.

```bash
uv run chat-cli db init
uv run chat-web
```

### Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `relation "chat_conversations" does not exist` (or a todo or cloud_agent table) | Schema not initialized. Run the matching Step 4 command. |
| Realtime endpoint closes with code 4503 | `AZURE_AI_PROJECT_ENDPOINT_REALTIME` is empty. Set it in Step 3. |
| PostgreSQL login or permission errors | Run `az login`, confirm `AZURE_DBUSER` is the Entra principal or role, and verify it has privileges on `AZURE_DBNAME`. |
| `DeprecationWarning` mentioning `CHAT_RESPONDER_BACKEND` | Remove that variable and use `CHAT_BOT_AGENT_TYPE`. |

### Related guides

* PostgreSQL server creation and Entra configuration: [Step 3 - PostgreSQL (pgvector) CRUD](03-postgres-vector-store.md)
* Observability with tracing and MLflow: [Step 2 - Observability](02-observability.md)
* App configuration details: [Chat App](../chat/index.md), [Cloud Agent App](../cloud_agent/index.md), [Knowledge Indexer](../knowledge/index.md)
* General development workflow: [Development Guide](../development.md)
