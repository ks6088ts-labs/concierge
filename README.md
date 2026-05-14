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

`concierge` is a Python hands-on repository that demonstrates how to build
LLM applications on top of **Microsoft Foundry** with **LangChain** and
**LangGraph**. It covers three themes - calling Foundry-hosted chat,
agent, embedding, and vector-store flows; adding observability through
**Azure Monitor / Foundry tracing** and **MLflow**; and persisting
embeddings in a **PostgreSQL (pgvector)** vector store, either locally
via **Docker Compose** or on **Azure Database for PostgreSQL Flexible
Server**.

### Prerequisites

#### Common (all topics)

* [Python 3.10+](https://www.python.org/downloads/)
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

### Where to go next

Detailed setup, CLI examples, and development commands are published on GitHub Pages.

* [concierge documentation](https://ks6088ts-labs.github.io/concierge/)
* [Chat app (clean architecture)](https://ks6088ts-labs.github.io/concierge/chat/)
* [Hands-on tutorial](https://ks6088ts-labs.github.io/concierge/tutorial/)
  * [Step 1 - Microsoft Foundry + LangChain](https://ks6088ts-labs.github.io/concierge/tutorial/01-foundry-langchain/)
  * [Step 2 - Observability (tracing & MLflow)](https://ks6088ts-labs.github.io/concierge/tutorial/02-observability/)
  * [Step 3 - PostgreSQL (pgvector) CRUD](https://ks6088ts-labs.github.io/concierge/tutorial/03-postgres-vector-store/)
* [Development guide](https://ks6088ts-labs.github.io/concierge/development/)

Every push to the `main` branch triggers the [github-pages workflow](.github/workflows/github-pages.yaml), which republishes the site.

---

## 日本語

### 概要

`concierge` は、**Microsoft Foundry** 上で **LangChain** / **LangGraph** を
使った LLM アプリケーションを構築するためのハンズオン Python リポジトリ
です。3 つのテーマを扱います — Foundry にホストされたチャット / エージェ
ント / 埋め込み / ベクトルストアの呼び出し、**Azure Monitor / Foundry
トレース**と **MLflow** による観測性の追加、そして **PostgreSQL
(pgvector)** によるベクトルストアへの埋め込み永続化 (ローカル **Docker
Compose** または **Azure Database for PostgreSQL Flexible Server**)。

### 前提条件

#### 共通 (全トピック)

* [Python 3.10+](https://www.python.org/downloads/)
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

### 関連リンク

詳細なセットアップ、CLI 実行例、開発コマンドは GitHub Pages にまとめています。

* [concierge ドキュメント (日本語)](https://ks6088ts-labs.github.io/concierge/ja/)
* [Chat アプリ (クリーンアーキテクチャ)](https://ks6088ts-labs.github.io/concierge/ja/chat/)
* [ハンズオンチュートリアル](https://ks6088ts-labs.github.io/concierge/ja/tutorial/)
  * [ステップ 1 - Microsoft Foundry + LangChain](https://ks6088ts-labs.github.io/concierge/ja/tutorial/01-foundry-langchain/)
  * [ステップ 2 - 観測性 (トレース & MLflow)](https://ks6088ts-labs.github.io/concierge/ja/tutorial/02-observability/)
  * [ステップ 3 - PostgreSQL (pgvector) CRUD](https://ks6088ts-labs.github.io/concierge/ja/tutorial/03-postgres-vector-store/)
* [開発ガイド](https://ks6088ts-labs.github.io/concierge/ja/development/)

`main` ブランチへの push で [github-pages workflow](.github/workflows/github-pages.yaml) が実行され、Pages が更新されます。
