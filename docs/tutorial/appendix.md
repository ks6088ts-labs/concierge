# Appendix - References

This page collects every external document referenced from the tutorial,
grouped by topic, so you have a single place to bookmark.

## Tooling

- [Python](https://www.python.org/downloads/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [GNU Make](https://www.gnu.org/software/make/)
- [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli)
- [Azure Developer CLI (`azd`)](https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/overview)

## LangChain & LangGraph

- [Install LangGraph](https://docs.langchain.com/oss/python/langgraph/install)
- [LangGraph Quickstart](https://docs.langchain.com/oss/python/langgraph/quickstart)
- [Connect with VS Code (MCP)](https://docs.langchain.com/use-these-docs#connect-with-vs-code)
- [langchain-ai/langchain-skills](https://github.com/langchain-ai/langchain-skills)
- [Microsoft provider integrations](https://docs.langchain.com/oss/python/integrations/providers/microsoft#azure-ai)
- [LangChain callbacks](https://docs.langchain.com/oss/python/langchain/callbacks)

## Microsoft Foundry

- [Microsoft Foundry overview](https://learn.microsoft.com/en-us/azure/foundry/)
- [Get started with LangChain and LangGraph on Foundry](https://learn.microsoft.com/en-us/azure/foundry/how-to/develop/langchain)
- [Use LangChain with models in Microsoft Foundry](https://learn.microsoft.com/en-us/azure/foundry/how-to/develop/langchain-models)
- [Trace LangChain and LangGraph apps with Foundry & Azure Monitor](https://learn.microsoft.com/en-us/azure/foundry/how-to/develop/langchain-traces)
- [Monitor generative AI applications (preview, classic)](https://learn.microsoft.com/en-us/azure/foundry-classic/how-to/monitor-applications)
- [`DefaultAzureCredential` reference](https://learn.microsoft.com/en-us/python/api/azure-identity/azure.identity.defaultazurecredential)

## MLflow

- [MLflow LangGraph integration](https://mlflow.org/docs/latest/genai/tracing/integrations/listing/langgraph/)
- [MLflow tracking server](https://mlflow.org/docs/latest/tracking.html)
- [MLflow GenAI Evaluation](https://mlflow.org/docs/latest/genai/)
- [MLflow built-in scorers](https://mlflow.org/docs/latest/genai/evaluation/builtin-judges/)
- [`@scorer` decorator](https://mlflow.org/docs/latest/genai/evaluation/custom-scorers/)

## Infrastructure as Code

- [microsoft/CAIRA](https://github.com/microsoft/CAIRA)
- [microsoft-foundry/foundry-samples - infrastructure](https://github.com/microsoft-foundry/foundry-samples/tree/main/infrastructure)

## PostgreSQL (pgvector) vector store

- [pgvector / pgvector](https://github.com/pgvector/pgvector)
- [pgvector/pgvector Docker image](https://hub.docker.com/r/pgvector/pgvector)
- [`langchain-postgres` package](https://pypi.org/project/langchain-postgres/)
- [`langchain-postgres` source](https://github.com/langchain-ai/langchain-postgres)
- [PGVector quickstart (LangChain docs)](https://docs.langchain.com/oss/python/langchain/rag#pgvector)

## Azure Database for PostgreSQL (pgvector)

- [Azure Database for PostgreSQL Flexible Server overview](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/overview)
- [Quickstart - create a Flexible Server (portal)](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/quickstart-create-server-portal)
- [Use the pgvector extension](https://learn.microsoft.com/en-us/azure/postgresql/extensions/how-to-use-pgvector)
- [Configure Microsoft Entra authentication](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/how-to-configure-sign-in-azure-ad-authentication)
- [Use LangChain with Azure Database for PostgreSQL](https://learn.microsoft.com/en-us/azure/postgresql/azure-ai/generative-ai-develop-with-langchain)

## Repository entry points

- [`README.md`](https://github.com/ks6088ts-labs/concierge/blob/main/README.md)
- [`Makefile`](https://github.com/ks6088ts-labs/concierge/blob/main/Makefile)
- [`pyproject.toml`](https://github.com/ks6088ts-labs/concierge/blob/main/pyproject.toml)
- [`compose.yml`](https://github.com/ks6088ts-labs/concierge/blob/main/compose.yml)
- [`.env.template`](https://github.com/ks6088ts-labs/concierge/blob/main/.env.template)
- [`scripts/microsoft_foundry/vanilla.py`](https://github.com/ks6088ts-labs/concierge/blob/main/scripts/microsoft_foundry/vanilla.py)
- [`scripts/mlflow/vanilla.py`](https://github.com/ks6088ts-labs/concierge/blob/main/scripts/mlflow/vanilla.py)
- [`scripts/postgresql/vanilla.py`](https://github.com/ks6088ts-labs/concierge/blob/main/scripts/postgresql/vanilla.py)
- [`concierge/settings/microsoft_foundry.py`](https://github.com/ks6088ts-labs/concierge/blob/main/concierge/settings/microsoft_foundry.py)
- [`concierge/settings/observability.py`](https://github.com/ks6088ts-labs/concierge/blob/main/concierge/settings/observability.py)
- [`concierge/settings/postgres.py`](https://github.com/ks6088ts-labs/concierge/blob/main/concierge/settings/postgres.py)
- [`concierge/settings/azure_postgres.py`](https://github.com/ks6088ts-labs/concierge/blob/main/concierge/settings/azure_postgres.py)
- [`concierge/settings/project.py`](https://github.com/ks6088ts-labs/concierge/blob/main/concierge/settings/project.py)
- [`concierge/loggers.py`](https://github.com/ks6088ts-labs/concierge/blob/main/concierge/loggers.py)
- [`concierge/observability.py`](https://github.com/ks6088ts-labs/concierge/blob/main/concierge/observability.py)
