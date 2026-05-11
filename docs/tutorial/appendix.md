# Appendix - References

This page collects every external document referenced from the tutorial,
grouped by topic, so you have a single place to bookmark.

## GitHub Issues that shaped the code

| # | Title                                  | State  | Link |
| - | :------------------------------------- | :----- | :--- |
| 1 | rename project                         | Closed | <https://github.com/ks6088ts-labs/concierge/issues/1> |
| 3 | set up LangGraph project               | Closed | <https://github.com/ks6088ts-labs/concierge/issues/3> |
| 5 | add tracing feature                    | Closed | <https://github.com/ks6088ts-labs/concierge/issues/5> |
| 6 | apply clean architecture               | Open   | <https://github.com/ks6088ts-labs/concierge/issues/6> |
| 8 | support MLflow locally for evaluation  | Closed | <https://github.com/ks6088ts-labs/concierge/issues/8> |
| 10 | set up infra via IaC                  | Open   | <https://github.com/ks6088ts-labs/concierge/issues/10> |

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

## Clean Architecture (Issue #6)

- [PacktPublishing/Clean-Architecture-with-Python](https://github.com/PacktPublishing/Clean-Architecture-with-Python)
- [*Pythonではじめるクリーンアーキテクチャ* (Impress)](https://book.impress.co.jp/books/1125101112)

## Infrastructure as Code (Issue #10)

- [microsoft/CAIRA](https://github.com/microsoft/CAIRA)
- [microsoft-foundry/foundry-samples - infrastructure](https://github.com/microsoft-foundry/foundry-samples/tree/main/infrastructure)

## Repository entry points

- [`README.md`](https://github.com/ks6088ts-labs/concierge/blob/main/README.md)
- [`Makefile`](https://github.com/ks6088ts-labs/concierge/blob/main/Makefile)
- [`pyproject.toml`](https://github.com/ks6088ts-labs/concierge/blob/main/pyproject.toml)
- [`.env.template`](https://github.com/ks6088ts-labs/concierge/blob/main/.env.template)
- [`scripts/microsoft_foundry/vanilla.py`](https://github.com/ks6088ts-labs/concierge/blob/main/scripts/microsoft_foundry/vanilla.py)
- [`concierge/settings/microsoft_foundry.py`](https://github.com/ks6088ts-labs/concierge/blob/main/concierge/settings/microsoft_foundry.py)
- [`concierge/settings/observability.py`](https://github.com/ks6088ts-labs/concierge/blob/main/concierge/settings/observability.py)
- [`concierge/settings/project.py`](https://github.com/ks6088ts-labs/concierge/blob/main/concierge/settings/project.py)
- [`concierge/loggers.py`](https://github.com/ks6088ts-labs/concierge/blob/main/concierge/loggers.py)
