# Hands-on Tutorial

Welcome to the **concierge** hands-on tutorial. This guide walks you through
the current application step by step.

Each step explains the **why** behind the change and shows runnable commands
plus selected code excerpts.

## Why follow this tutorial?

The repository is a template for building LLM applications on top of
[Microsoft Foundry](https://learn.microsoft.com/en-us/azure/foundry/) with
[LangChain](https://docs.langchain.com/) and
[LangGraph](https://docs.langchain.com/oss/python/langgraph/quickstart). Rather
than reading the finished code in isolation, you will build it up step by step
so the design decisions stay visible.

## Tutorial map

| Step | Topic                                |
| :--- | :----------------------------------- |
| 1    | Microsoft Foundry + LangChain setup  |
| 2a   | Tracing with Azure Monitor / Foundry |
| 2b   | Local evaluation with MLflow         |
| 3    | PostgreSQL (pgvector) CRUD - Docker Compose or Azure Flexible Server |
| 4    | LangGraph Todo Agent CLI             |

Steps 1 and 2 build the Foundry + LangChain CLI and add observability.
Step 3 adds a persistent vector store backed by PostgreSQL with pgvector and
walks through the same CRUD workflow against two interchangeable targets - a
local Docker Compose service or a managed Azure Database for PostgreSQL
Flexible Server - using a single CLI
(`scripts/postgresql/vanilla.py --target docker|azure`).
Step 4 adds a LangGraph-based Todo agent CLI (`scripts/langgraph/vanilla.py`)
that operates the existing Todo Web API through tools in one-shot (`run`) or
interactive (`chat`) mode.

## High-level architecture

```mermaid
flowchart LR
    User([Developer])
    CLI["Typer CLI<br/>scripts/microsoft_foundry/vanilla.py"]
    Settings["Pydantic settings<br/>concierge/settings/*"]
    LC["LangChain / LangGraph"]
    Foundry[("Microsoft Foundry<br/>Project endpoint")]
    Models["Foundry-hosted models<br/>gpt-5, text-embedding-3-small, ..."]
    Tracer["AzureAIOpenTelemetryTracer"]
    Monitor[("Azure Monitor")]
    MLflow[("MLflow Tracking<br/>http://127.0.0.1:5000")]

    User --> CLI
    CLI --> Settings
    CLI --> LC
    LC -->|"chat / embeddings / agent"| Foundry
    Foundry --> Models
    LC -.->|"--tracing"| Tracer --> Monitor
    LC -.->|"--mlflow autolog"| MLflow
```

## Prerequisites

Before starting, make sure your machine has the following installed. Versions
align with what the repository's [`pyproject.toml`](https://github.com/ks6088ts-labs/concierge/blob/main/pyproject.toml)
and [`Makefile`](https://github.com/ks6088ts-labs/concierge/blob/main/Makefile)
expect.

- [Python 3.10+](https://www.python.org/downloads/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) - dependency
  and virtual-env manager used by every `make` target
- [GNU Make](https://www.gnu.org/software/make/) - thin wrapper around the
  `uv` commands
- An Azure subscription with access to [Microsoft Foundry](https://ai.azure.com/)
  and deployed chat / embedding models. The examples use the default deployment
  names from the code (`gpt-5` and `text-embedding-3-small`), but you should
  replace them with the deployment names available in your project.
- [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli)
  signed in (`az login`) so `DefaultAzureCredential` can pick up your identity

!!! tip "Why `DefaultAzureCredential`?"
    The CLI in this repo authenticates via
    [`DefaultAzureCredential`](https://learn.microsoft.com/en-us/python/api/azure-identity/azure.identity.defaultazurecredential),
    which transparently uses `az login`, managed identity, environment
    variables, or a developer credential. You do not need to manage API keys.

## How to read each step

Every step page is structured the same way so you can pattern-match quickly:

1. **Goal** - the user value the step unlocks.
2. **Why** - the design rationale.
3. **Steps** - runnable commands and selected code excerpts.
4. **Verify** - how to confirm the change works.
5. **Troubleshooting** - common pitfalls and fixes.

Continue with [Step 1 - Microsoft Foundry + LangChain](01-foundry-langchain.md).
