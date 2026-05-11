# Appendix - 参考資料

チュートリアル中で参照した外部資料をトピック別にまとめています。後から
戻ってくる際のブックマーク用ページとして活用してください。

## コードに反映された GitHub Issue

| # | タイトル                              | 状態   | リンク |
| - | :------------------------------------ | :----- | :----- |
| 1 | rename project                        | Closed | <https://github.com/ks6088ts-labs/concierge/issues/1> |
| 3 | set up LangGraph project              | Closed | <https://github.com/ks6088ts-labs/concierge/issues/3> |
| 5 | add tracing feature                   | Closed | <https://github.com/ks6088ts-labs/concierge/issues/5> |
| 6 | apply clean architecture              | Open   | <https://github.com/ks6088ts-labs/concierge/issues/6> |
| 8 | support MLflow locally for evaluation | Closed | <https://github.com/ks6088ts-labs/concierge/issues/8> |
| 10 | set up infra via IaC                 | Open   | <https://github.com/ks6088ts-labs/concierge/issues/10> |

## ツール

- [Python](https://www.python.org/downloads/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [GNU Make](https://www.gnu.org/software/make/)
- [Azure CLI](https://learn.microsoft.com/ja-jp/cli/azure/install-azure-cli)
- [Azure Developer CLI (`azd`)](https://learn.microsoft.com/ja-jp/azure/developer/azure-developer-cli/overview)

## LangChain & LangGraph

- [Install LangGraph](https://docs.langchain.com/oss/python/langgraph/install)
- [LangGraph クイックスタート](https://docs.langchain.com/oss/python/langgraph/quickstart)
- [VS Code (MCP) で接続](https://docs.langchain.com/use-these-docs#connect-with-vs-code)
- [langchain-ai/langchain-skills](https://github.com/langchain-ai/langchain-skills)
- [Microsoft プロバイダ統合](https://docs.langchain.com/oss/python/integrations/providers/microsoft#azure-ai)
- [LangChain コールバック](https://docs.langchain.com/oss/python/langchain/callbacks)

## Microsoft Foundry

- [Microsoft Foundry の概要](https://learn.microsoft.com/ja-jp/azure/foundry/)
- [Foundry での LangChain / LangGraph の入門](https://learn.microsoft.com/ja-jp/azure/foundry/how-to/develop/langchain)
- [Microsoft Foundry のモデルを LangChain から利用する](https://learn.microsoft.com/ja-jp/azure/foundry/how-to/develop/langchain-models)
- [Foundry & Azure Monitor で LangChain / LangGraph をトレースする](https://learn.microsoft.com/ja-jp/azure/foundry/how-to/develop/langchain-traces)
- [生成 AI アプリケーションを監視する (プレビュー・クラシック)](https://learn.microsoft.com/ja-jp/azure/foundry-classic/how-to/monitor-applications)
- [`DefaultAzureCredential` リファレンス](https://learn.microsoft.com/ja-jp/python/api/azure-identity/azure.identity.defaultazurecredential)

## MLflow

- [MLflow LangGraph 連携](https://mlflow.org/docs/latest/genai/tracing/integrations/listing/langgraph/)
- [MLflow tracking サーバ](https://mlflow.org/docs/latest/tracking.html)

## クリーンアーキテクチャ (Issue #6)

- [PacktPublishing/Clean-Architecture-with-Python](https://github.com/PacktPublishing/Clean-Architecture-with-Python)
- [*Pythonではじめるクリーンアーキテクチャ* (Impress)](https://book.impress.co.jp/books/1125101112)

## IaC (Issue #10)

- [microsoft/CAIRA](https://github.com/microsoft/CAIRA)
- [microsoft-foundry/foundry-samples - infrastructure](https://github.com/microsoft-foundry/foundry-samples/tree/main/infrastructure)

## リポジトリ内エントリポイント

- [`README.md`](https://github.com/ks6088ts-labs/concierge/blob/main/README.md)
- [`Makefile`](https://github.com/ks6088ts-labs/concierge/blob/main/Makefile)
- [`pyproject.toml`](https://github.com/ks6088ts-labs/concierge/blob/main/pyproject.toml)
- [`.env.template`](https://github.com/ks6088ts-labs/concierge/blob/main/.env.template)
- [`scripts/microsoft_foundry/vanilla.py`](https://github.com/ks6088ts-labs/concierge/blob/main/scripts/microsoft_foundry/vanilla.py)
- [`concierge/settings/microsoft_foundry.py`](https://github.com/ks6088ts-labs/concierge/blob/main/concierge/settings/microsoft_foundry.py)
- [`concierge/settings/observability.py`](https://github.com/ks6088ts-labs/concierge/blob/main/concierge/settings/observability.py)
- [`concierge/settings/project.py`](https://github.com/ks6088ts-labs/concierge/blob/main/concierge/settings/project.py)
- [`concierge/loggers.py`](https://github.com/ks6088ts-labs/concierge/blob/main/concierge/loggers.py)
