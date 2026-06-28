---
title: 付録 - Azure 環境セットアップ
description: concierge を Azure 上で動かすための通し手順。Foundry エンドポイント、Azure Database for PostgreSQL、スキーマ初期化までを扱う
---

## Azure 環境セットアップ

clone 直後の状態から、Azure をバックエンドにした concierge が動くところまでを順番に進めます。LLM・リアルタイム・画像生成それぞれの Foundry エンドポイントと、永続化用の Azure Database for PostgreSQL を設定します。

!!! note

    ローカルのみ（Docker pgvector、Azure 非依存）で開発する場合は、本付録ではなく [開発ガイド](../development.md) とチュートリアル 1〜3 を参照してください。本付録はマネージドな Azure 構成を対象とします。

### この付録で設定するもの

* チャット/LLM・リアルタイム音声・画像生成の Foundry プロジェクトエンドポイント
* Microsoft Entra 認証による Azure Database for PostgreSQL 接続
* Todo・Chat・Cloud Agent 各アプリの永続化バックエンド
* （任意）Azure PostgreSQL を対象とするナレッジ検索と、永続的な Cloud Agent キュー

### 前提

依存関係をインストールし、環境変数テンプレートをコピーしてサインインします。

```bash
make install-deps-dev
cp .env.template .env
az login
```

サブスクリプション側には次が必要です。

* 利用するモデルがデプロイ済みの Azure AI Foundry (AIServices) リソース（1 つ以上）。
* `pgvector` 拡張が利用できる Azure Database for PostgreSQL Flexible Server。
* ストレージアカウント（永続的な Cloud Agent キューを使う場合のみ）。

必要なアクセス権は次のとおりです。

* 参照する各 Foundry プロジェクトに対する "Azure AI Developer" ロール。
* PostgreSQL が認識する Microsoft Entra プリンシパル（サーバの Entra 管理者、または自分のプリンシパルに紐づくロール）。
* キューを使う場合はストレージアカウントに対する "Storage Queue Data Contributor" ロール。

### ステップ 1: リソースを調べる

以下の参照系コマンドを実行し、出力を手元に残します。ここで得た値をステップ 3 で `.env` に貼り付けます。

```bash
# 現在のサブスクリプションとサインインユーザー
az account show --query "{name:name, id:id, user:user.name}" -o json

# Foundry (AIServices) アカウント一覧
az cognitiveservices account list \
  --query "[].{name:name, kind:kind, location:location, rg:resourceGroup}" -o table

# 1 アカウントのモデルデプロイ一覧（アカウントごとに繰り返す）
az cognitiveservices account deployment list -g <rg> -n <account> \
  --query "[].{name:name, model:properties.model.name}" -o table

# Foundry プロジェクト名（エンドポイントのパスに使う）
az rest --method get \
  --url "https://management.azure.com/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<account>/projects?api-version=2025-04-01-preview" \
  --query "value[].name" -o json

# PostgreSQL Flexible Server
az postgres flexible-server list \
  --query "[].{name:name, fqdn:fullyQualifiedDomainName, rg:resourceGroup, version:version}" -o table

# PostgreSQL の Microsoft Entra 管理者（トークンでサインインできる主体）
az postgres flexible-server microsoft-entra-admin list -g <rg> --server-name <server> \
  --query "[].principalName" -o json

# ストレージアカウント（任意、Cloud Agent キュー用）
az storage account list --query "[].{name:name, queue:primaryEndpoints.queue}" -o table
```

!!! tip

    Foundry プロジェクトエンドポイントは常に `https://<account>.services.ai.azure.com/api/projects/<project>` の形になります。projects の呼び出しは `<account>/<project>` を返すので、スラッシュより後ろが `<project>` です。Azure CLI 2.86 より前では管理者コマンドは `microsoft-entra-admin` ではなく `ad-admin` です。

### ステップ 2: デプロイと Foundry エンドポイントの対応付け

concierge は最大 3 つの Foundry プロジェクトを使い分けられます。ホストしているモデルデプロイに基づいて選びます。

| 変数 | ホストしている Foundry プロジェクトを指定 |
|---|---|
| `AZURE_AI_PROJECT_ENDPOINT` | チャット/LLM と埋め込み（例: gpt-5, gpt-4o, text-embedding-3-small） |
| `AZURE_AI_PROJECT_ENDPOINT_REALTIME` | リアルタイムモデル（例: gpt-realtime-1.5）。別リージョンのことが多い |
| `AZURE_AI_PROJECT_ENDPOINT_IMAGE` | 画像モデル（gpt-image-2）。提供リージョンが限られる |

!!! note

    1 つの Foundry リソースで 3 つすべてをホストすることもできます。エンドポイントを分けるのは、リアルタイムと画像のモデルが基本のチャットモデルより提供リージョンが少ないためです。

### ステップ 3: .env を記入する

[.env.template](https://github.com/ks6088ts-labs/concierge/blob/main/.env.template) からコピーした `.env` を編集します。次のブロックが Azure 構成での最小設定です。`<...>` のプレースホルダはステップ 1 の値に置き換えます。

```dotenv
# --- Foundry エンドポイント（ステップ 2 を参照）---
AZURE_AI_PROJECT_ENDPOINT=https://<llm-account>.services.ai.azure.com/api/projects/<project>
AZURE_AI_PROJECT_ENDPOINT_REALTIME=https://<realtime-account>.services.ai.azure.com/api/projects/<project>
AZURE_AI_PROJECT_ENDPOINT_IMAGE=https://<image-account>.services.ai.azure.com/api/projects/<project>

# --- Azure Database for PostgreSQL（Microsoft Entra 認証）---
AZURE_DBHOST=<server-name>.postgres.database.azure.com
AZURE_DBNAME=appdb
AZURE_DBUSER=<entra-principal>
AZURE_USE_ENTRA_AUTH=true

# --- 各アプリの永続化を Azure PostgreSQL にする ---
TODO_REPOSITORY_BACKEND=azure-postgres
CHAT_REPOSITORY_BACKEND=azure-postgres
CLOUD_AGENT_REPOSITORY_BACKEND=azure-postgres

# --- チャット応答をストリーミング Foundry レスポンダーにする ---
CHAT_BOT_AGENT_TYPE=foundry
```

該当する任意機能を使う場合のみ、次を追加します。

```dotenv
# Azure PostgreSQL を対象とするナレッジ検索ツール
AGENTS_KNOWLEDGE__TOOLS=search_docs
AGENTS_KNOWLEDGE__TARGET=azure
AGENTS_KNOWLEDGE__SEARCH_DOCS__COLLECTION=knowledge_default

# 永続的な Cloud Agent キュー
CLOUD_AGENT_QUEUE_BACKEND=azure-storage-queue
CLOUD_AGENT_AZURE_STORAGE_ACCOUNT_URL=https://<account>.queue.core.windows.net
```

!!! warning "AZURE_DBUSER は認識される Entra プリンシパルであること"

    `AZURE_DBUSER` は PostgreSQL が認識する Microsoft Entra プリンシパルである必要があります。サーバの Entra 管理者であればそのままテーブルを作成できます。それ以外のプリンシパルでは、先に対応するデータベースロールを作成して権限を付与してください。Entra の構成手順は [PostgreSQL チュートリアル](03-postgres-vector-store.md) にあります。

!!! note "レスポンダーとツールの利用可否"

    `CHAT_RESPONDER_BACKEND` は非推奨で警告を出すため、`CHAT_BOT_AGENT_TYPE` のみを使います。`foundry` レスポンダーは応答をストリーミングしますがエージェントツールは呼び出しません。そのためテキストチャットでナレッジツールを使うには `CHAT_BOT_AGENT_TYPE=langgraph` を設定します。リアルタイム音声はレスポンダーに関係なくナレッジツールを含みます。

### ステップ 4: データベーススキーマを初期化する

CLI 用の SQL バックエンドは自動マイグレーションしないため、アプリごとに一度テーブルを作成します。

```bash
uv run chat-cli db init     # chat_conversations, chat_participants, chat_messages
uv run todo-cli db init     # todo_tasks
```

Cloud Agent の web / worker は起動時に `cloud_agent_tasks` を自動作成します。事前に作成する場合は次を実行します。

```bash
uv run python -c "from dotenv import load_dotenv; load_dotenv(); from concierge.cloud_agent.infrastructure.persistence.factory import get_task_repository; get_task_repository()"
```

ナレッジツールを有効化した場合は、コレクションへデータを投入します。テーブルは最初の ingest 時に作成されます。

```bash
uv run knowledge-cli ingest run ./docs --collection knowledge_default --target azure
```

すべての DDL は `CREATE TABLE IF NOT EXISTS` を使うため、再実行しても安全です。

### ステップ 5: 確認する

冪等な再実行が成功すれば、スキーマが存在することを確認できます。アプリを起動して動作確認することもできます。

```bash
uv run chat-cli db init
uv run chat-web
```

### トラブルシューティング

| 症状 | 原因と対処 |
|---|---|
| `relation "chat_conversations" does not exist`（または todo / cloud_agent のテーブル） | スキーマ未初期化。該当するステップ 4 のコマンドを実行する。 |
| リアルタイムエンドポイントがコード 4503 で切断される | `AZURE_AI_PROJECT_ENDPOINT_REALTIME` が未設定。ステップ 3 で設定する。 |
| PostgreSQL のログインまたは権限エラー | `az login` を実行し、`AZURE_DBUSER` が Entra プリンシパル/ロールであること、`AZURE_DBNAME` に対する権限があることを確認する。 |
| `CHAT_RESPONDER_BACKEND` に関する `DeprecationWarning` | その変数を削除し、`CHAT_BOT_AGENT_TYPE` を使う。 |

### 関連ガイド

* PostgreSQL サーバ作成と Entra 構成: [ステップ 3 - PostgreSQL (pgvector) CRUD](03-postgres-vector-store.md)
* トレーシングと MLflow による observability: [ステップ 2 - Observability](02-observability.md)
* アプリ設定の詳細: [Chat App](../chat/index.md), [Cloud Agent App](../cloud_agent/index.md), [Knowledge Indexer](../knowledge/index.md)
* 一般的な開発ワークフロー: [開発ガイド](../development.md)
