---
title: concierge
description: Microsoft Foundry, LangChain, and LangGraph hands-on examples with observability
---

[![test](https://github.com/ks6088ts-labs/concierge/actions/workflows/test.yaml/badge.svg?branch=main)](https://github.com/ks6088ts-labs/concierge/actions/workflows/test.yaml?query=branch%3Amain)
[![docker](https://github.com/ks6088ts-labs/concierge/actions/workflows/docker.yaml/badge.svg?branch=main)](https://github.com/ks6088ts-labs/concierge/actions/workflows/docker.yaml?query=branch%3Amain)
[![docker-release](https://github.com/ks6088ts-labs/concierge/actions/workflows/docker-release.yaml/badge.svg)](https://github.com/ks6088ts-labs/concierge/actions/workflows/docker-release.yaml)
[![ghcr-release](https://github.com/ks6088ts-labs/concierge/actions/workflows/ghcr-release.yaml/badge.svg)](https://github.com/ks6088ts-labs/concierge/actions/workflows/ghcr-release.yaml)
[![docs](https://github.com/ks6088ts-labs/concierge/actions/workflows/github-pages.yaml/badge.svg)](https://github.com/ks6088ts-labs/concierge/actions/workflows/github-pages.yaml)

> **Language / 言語**: [English](#english) · [日本語](#日本語)

---

## English

### Overview

`concierge` is a Python hands-on **reference repository** for building
production-style LLM applications on **Microsoft Foundry**. Each
feature ships as an independently-deployable bounded context with a
shared `concierge.settings` configuration layer and a strict
clean-architecture (`domain` / `application` / `infrastructure`)
layout that is enforced in CI by
[`import-linter`](https://import-linter.readthedocs.io/).

#### What you can learn here

* **LLM application architecture** — how to keep `langchain`,
  `langgraph`, `agent-framework`, `github-copilot-sdk`, and the Foundry
  SDK behind interface boundaries instead of leaking into your domain.
* **Multi-runtime agent adapters** — a single `AgentRegistry` swaps
  between LangGraph, the Microsoft Agent Framework, the GitHub Copilot
  SDK, and a deterministic Echo backend through the same protocol.
* **Retrieval & RAG plumbing** — Markdown ingest + `pgvector` via
  `langchain-postgres`, driven by a Typer CLI against Docker Compose
  pgvector or Azure Database for PostgreSQL Flexible Server (passwordless
  Entra-ID auth supported).
* **End-to-end observability** — Foundry / Azure Monitor tracing for
  LangChain runs, plus an MLflow autologging path you can run locally
  with `make mlflow`.
* **Async agent execution** — a `cloud_agent` service that dispatches
  jobs through **Azure Queue Storage** and reports state through a
  repository + REST API.
* **Realtime voice** — a websocket bridge to Foundry realtime models
  exposed from the `chat` service.

#### What's inside

| Service | Surfaces | What it does |
| :--- | :--- | :--- |
| `todo` | FastAPI + Typer | CRUD reference app; the smallest fully-tested clean-architecture slice |
| `knowledge` | Typer CLI | Markdown indexer + pgvector retrieval (`ingest` / `search` / `drop`) |
| `agents` | Typer CLI | Shared agent runtime with pluggable adapters and built-in tools (echo, files, shell, image gen, knowledge retrieval) |
| `chat` | FastAPI + Typer + Realtime WebSocket | Synchronous chat replies and realtime voice over Foundry models |
| `cloud_agent` | FastAPI + Typer | Async job dispatcher backed by Azure Queue Storage |

#### Tech stack at a glance

Python 3.11+,
[uv](https://docs.astral.sh/uv/) ·
[FastAPI](https://fastapi.tiangolo.com/) ·
[Typer](https://typer.tiangolo.com/) ·
[Pydantic-Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) ·
[LangChain 1.x](https://docs.langchain.com/) /
[LangGraph 1.x](https://docs.langchain.com/oss/python/langgraph/quickstart) ·
[Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/overview/agent-framework-overview) ·
[GitHub Copilot SDK](https://github.com/microsoft/github-copilot-sdk-python) ·
[langchain-postgres](https://pypi.org/project/langchain-postgres/) (pgvector) ·
[Azure Queue Storage](https://learn.microsoft.com/en-us/azure/storage/queues/) ·
[MLflow 3.x](https://mlflow.org/) ·
[testcontainers](https://testcontainers-python.readthedocs.io/) for integration tests.

### Prerequisites

#### Common (all topics)

* [Python 3.11+](https://www.python.org/downloads/)
* [uv](https://docs.astral.sh/uv/getting-started/installation/) — dependency resolution and virtual environment management driven from `make` targets
* [GNU Make](https://www.gnu.org/software/make/) — a thin wrapper around `uv` commands

#### Tutorial

##### Step 1 - Microsoft Foundry + LangChain

* A Microsoft Foundry project with a chat model and an embedding model deployed
* [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) signed in via `az login` (used by `DefaultAzureCredential`)

##### Step 2 - Observability (tracing & MLflow)

* Tracing enabled on the Foundry project, with the `Azure AI Developer` role assigned to your identity
* A local MLflow server (the repository ships a `make mlflow` target that runs it)

##### Step 3 - PostgreSQL (pgvector) CRUD

* A PostgreSQL instance with the [pgvector extension](https://github.com/pgvector/pgvector) — either local via [Docker Compose](https://docs.docker.com/compose/install/), or [Azure Database for PostgreSQL Flexible Server](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/overview) with [Microsoft Entra authentication](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/how-to-configure-sign-in-azure-ad-authentication)

##### Step 4 - LangGraph Todo Agent CLI

* The Todo Web API running locally (`uv run todo-web`) so the LangGraph agent has a tool target to call over HTTP
* The same Foundry credentials used in Step 1

### Where to go next

Detailed setup, CLI examples, and development commands are published on GitHub Pages.

* [concierge documentation](https://ks6088ts-labs.github.io/concierge/)
* [Todo app (clean architecture)](https://ks6088ts-labs.github.io/concierge/todo/)
* [Knowledge service (Markdown → pgvector)](https://ks6088ts-labs.github.io/concierge/knowledge/)
* [Agents runtime (adapters & tools)](https://ks6088ts-labs.github.io/concierge/agents/)
* [Chat app (REST + Realtime)](https://ks6088ts-labs.github.io/concierge/chat/)
* [Cloud Agent app (async dispatcher)](https://ks6088ts-labs.github.io/concierge/cloud_agent/)
* [Hands-on tutorial](https://ks6088ts-labs.github.io/concierge/tutorial/)
  * [Step 1 - Microsoft Foundry + LangChain](https://ks6088ts-labs.github.io/concierge/tutorial/01-foundry-langchain/)
  * [Step 2 - Observability (tracing & MLflow)](https://ks6088ts-labs.github.io/concierge/tutorial/02-observability/)
  * [Step 3 - PostgreSQL (pgvector) CRUD](https://ks6088ts-labs.github.io/concierge/tutorial/03-postgres-vector-store/)
  * [Step 4 - LangGraph Todo Agent CLI](https://ks6088ts-labs.github.io/concierge/tutorial/04-langgraph-todo-agent/)
* [Development guide](https://ks6088ts-labs.github.io/concierge/development/)

Every push to the `main` branch triggers the [github-pages workflow](.github/workflows/github-pages.yaml), which republishes the site.

---

## 日本語

### 概要

`concierge` は、**Microsoft Foundry** 上で本番品質の LLM アプリケーションを
構築するための Python **リファレンス実装**リポジトリです。各サービスは
独立したバウンデッドコンテキストとして出荷され、共通の
`concierge.settings` 設定層と、`domain` / `application` /
`infrastructure` のクリーンアーキテクチャ層を共有します。層間の
依存方向は CI 上で
[`import-linter`](https://import-linter.readthedocs.io/) によって強制されます。

#### ここで学べること

* **LLM アプリケーション設計** — `langchain` / `langgraph` /
  `agent-framework` / `github-copilot-sdk` / Foundry SDK をドメインに漏れさせず
  インタフェース境界の裏側に隔離する実装パターン。
* **複数ランタイムのエージェントアダプタ** — 1 つの `AgentRegistry` で
  LangGraph / Microsoft Agent Framework / GitHub Copilot SDK /
  決定論的な Echo バックエンドを同じプロトコルで差し替える仕組み。
* **検索 / RAG の配管** — Markdown をインジェストして
  `langchain-postgres` 経由で `pgvector` に永続化、Typer CLI から
  Docker Compose pgvector または Azure Database for PostgreSQL Flexible
  Server (パスワードレスな Entra ID 認証対応) を選べるパイプライン。
* **End-to-End な観測性** — LangChain 実行を Foundry / Azure Monitor
  へトレースし、`make mlflow` で起動できるローカル MLflow へも
  autologging する二重の可視化パス。
* **非同期エージェント実行** — **Azure Queue Storage** を介してジョブを
  ディスパッチし、リポジトリ + REST API で状態を返す `cloud_agent`。
* **リアルタイム音声** — `chat` サービスから提供される Foundry
  リアルタイムモデルとの WebSocket ブリッジ。

#### 収録サービス

| サービス | サーフェース | 内容 |
| :--- | :--- | :--- |
| `todo` | FastAPI + Typer | CRUD リファレンスアプリ。テスト完備の最小のクリーンアーキテクチャサンプル |
| `knowledge` | Typer CLI | Markdown インデクサ + pgvector 検索 (`ingest` / `search` / `drop`) |
| `agents` | Typer CLI | 交換可能なエージェントランタイムと組み込みツール (echo / files / shell / image gen / knowledge retrieval) |
| `chat` | FastAPI + Typer + Realtime WebSocket | 同期チャット応答と Foundry リアルタイム音声 |
| `cloud_agent` | FastAPI + Typer | Azure Queue Storage を背後に持つ非同期ジョブディスパッチャ |

#### 主要テクノロジースタック

Python 3.11+,
[uv](https://docs.astral.sh/uv/) ·
[FastAPI](https://fastapi.tiangolo.com/) ·
[Typer](https://typer.tiangolo.com/) ·
[Pydantic-Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) ·
[LangChain 1.x](https://docs.langchain.com/) /
[LangGraph 1.x](https://docs.langchain.com/oss/python/langgraph/quickstart) ·
[Microsoft Agent Framework](https://learn.microsoft.com/ja-jp/agent-framework/overview/agent-framework-overview) ·
[GitHub Copilot SDK](https://github.com/microsoft/github-copilot-sdk-python) ·
[langchain-postgres](https://pypi.org/project/langchain-postgres/) (pgvector) ·
[Azure Queue Storage](https://learn.microsoft.com/ja-jp/azure/storage/queues/) ·
[MLflow 3.x](https://mlflow.org/) ·
統合テストには [testcontainers](https://testcontainers-python.readthedocs.io/) を使用。

### 前提条件

#### 共通 (全トピック)

* [Python 3.11+](https://www.python.org/downloads/)
* [uv](https://docs.astral.sh/uv/getting-started/installation/) — 依存解決と仮想環境を `make` ターゲットから一元管理
* [GNU Make](https://www.gnu.org/software/make/) — `uv` コマンドを包む薄いラッパー

#### チュートリアル

##### ステップ 1 - Microsoft Foundry + LangChain

* チャットモデルと埋め込みモデルがデプロイされた Microsoft Foundry プロジェクト
* [Azure CLI](https://learn.microsoft.com/ja-jp/cli/azure/install-azure-cli) で `az login` 済み (`DefaultAzureCredential` が利用)

##### ステップ 2 - 観測性 (トレース & MLflow)

* Foundry プロジェクトでトレースが有効化されており、自分の ID に `Azure AI Developer` ロールが付与されていること
* ローカル MLflow サーバ (本リポジトリには `make mlflow` ターゲットが付属)

##### ステップ 3 - PostgreSQL (pgvector) CRUD

* [pgvector 拡張](https://github.com/pgvector/pgvector) を有効化した PostgreSQL — ローカル [Docker Compose](https://docs.docker.com/compose/install/) でも、[Microsoft Entra 認証](https://learn.microsoft.com/ja-jp/azure/postgresql/flexible-server/how-to-configure-sign-in-azure-ad-authentication) を構成した [Azure Database for PostgreSQL Flexible Server](https://learn.microsoft.com/ja-jp/azure/postgresql/flexible-server/overview) でも可

##### ステップ 4 - LangGraph Todo Agent CLI

* Todo Web API がローカルで起動していること (`uv run todo-web`)。LangGraph エージェントが HTTP ツールから呼び出します
* ステップ 1 と同じ Foundry 認証情報

### 関連リンク

詳細なセットアップ、CLI 実行例、開発コマンドは GitHub Pages にまとめています。

* [concierge ドキュメント (日本語)](https://ks6088ts-labs.github.io/concierge/ja/)
* [Todo アプリ (クリーンアーキテクチャ)](https://ks6088ts-labs.github.io/concierge/ja/todo/)
* [Knowledge サービス (Markdown → pgvector)](https://ks6088ts-labs.github.io/concierge/ja/knowledge/)
* [Agents ランタイム (アダプタとツール)](https://ks6088ts-labs.github.io/concierge/ja/agents/)
* [Chat アプリ (REST + Realtime)](https://ks6088ts-labs.github.io/concierge/ja/chat/)
* [Cloud Agent アプリ (非同期ディスパッチャ)](https://ks6088ts-labs.github.io/concierge/ja/cloud_agent/)
* [ハンズオンチュートリアル](https://ks6088ts-labs.github.io/concierge/ja/tutorial/)
  * [ステップ 1 - Microsoft Foundry + LangChain](https://ks6088ts-labs.github.io/concierge/ja/tutorial/01-foundry-langchain/)
  * [ステップ 2 - 観測性 (トレース & MLflow)](https://ks6088ts-labs.github.io/concierge/ja/tutorial/02-observability/)
  * [ステップ 3 - PostgreSQL (pgvector) CRUD](https://ks6088ts-labs.github.io/concierge/ja/tutorial/03-postgres-vector-store/)
  * [ステップ 4 - LangGraph Todo Agent CLI](https://ks6088ts-labs.github.io/concierge/ja/tutorial/04-langgraph-todo-agent/)
* [開発ガイド](https://ks6088ts-labs.github.io/concierge/ja/development/)

`main` ブランチへの push で [github-pages workflow](.github/workflows/github-pages.yaml) が実行され、Pages が更新されます。
