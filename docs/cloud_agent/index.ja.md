---
title: Cloud Agent App (日本語)
description: DDDクリーンアーキテクチャによる非同期タスクディスパッチ
---

## 概要

`concierge/cloud_agent` は、**クリーンアーキテクチャ**（DDDレイヤード構造）で
実装された非同期タスクディスパッチアプリケーションです。REST API 経由でタスクを
受け取り、バックグラウンドキューを通じて適切なエージェントに割り当て、結果を
返します。

```mermaid
flowchart LR
    Client[REST クライアント] --> Web[FastAPI ルート]
    Web --> UC[アプリケーションユースケース]
    CLI[Typer CLI / ワーカー] --> UC
    UC --> Domain[ドメインエンティティ]
    UC --> Repo[TaskRepository]
    UC --> Queue[TaskQueue]
    UC --> Registry[AgentRegistry]
    Registry --> Echo[EchoAgent]
    Registry --> LG["LangGraphAgent\n(langgraph)"]
    Registry --> GCE[GitHubCopilotEchoAgent]
    Registry --> MAF["MicrosoftAgentFrameworkAgent\n(microsoft-agent-framework)"]
```

## エージェント拡張ポイント

エージェントは共有バウンデッドコンテキスト `concierge/agents/` で定義されます。
各エージェントは共有 `application` 層の `Agent` Protocol を実装します。

```python
class Agent(Protocol):
    # ``ClassVar[str]`` とインスタンス属性のどちらも受け入れるよう
    # プレーンな属性宣言にしてある。
    agent_type: str
    async def handle(self, request: AgentRequest) -> AgentResponse: ...
```

LangChain / LangGraph のインポートは `infrastructure` 層のみに許可されます。
`domain` 層・`application` 層はフレームワーク非依存を維持します
（`tests/agents/test_architecture.py` と import-linter 契約で機械的に検証）。

```mermaid
classDiagram
    class Agent {
        <<Protocol>>
        +agent_type: str
        +handle(request) AgentResponse
    }
    class EchoAgent {
        +agent_type = "echo"
        +handle(request) AgentResponse
    }
    class LangGraphAgent {
        +agent_type (インスタンス)
        +tool_builders
        +handle(request) AgentResponse
        -_build_agent(side_outputs)
    }
    class GitHubCopilotEchoAgent {
        +agent_type = "github-copilot-echo"
        +handle(request) AgentResponse
    }
    class MicrosoftAgentFrameworkAgent {
        +agent_type (インスタンス)
        +tool_builders
        +handle(request) AgentResponse
        -_build_agent(side_outputs)
    }
    Agent <|.. EchoAgent
    Agent <|.. LangGraphAgent
    Agent <|.. GitHubCopilotEchoAgent
    Agent <|.. MicrosoftAgentFrameworkAgent
```

## 主要な設計方針

- **キュー非依存の抽象化** — `InMemory`（ローカル開発）と
  `AzureStorageQueue` の 2 実装を提供。`CLOUD_AGENT_QUEUE_BACKEND` で切り替え可能。
- **エージェント I/O の標準化** — すべてのエージェントは `AgentRequest` を受け取り、
  `AgentResponse` を返す（`concierge.agents` の Pydantic スキーマ）。`AgentRegistry` が
  `agent_type` 文字列を具体的な `Agent` 実装にマッピングする。
- **実行環境非依存のワーカー** — 現在はローカル CLI プロセスとして動作するが、
  同じ `Agent` インタフェースを将来 Azure Functions でも再利用できる。
- **Dead Letter Queue（DLQ）** — `max_retries` を超えたタスクは自動的に DLQ に移動される。

## ディレクトリ構成

```
concierge/cloud_agent/
  domain/
    entities.py        # Task データクラス（状態機械遷移付き）
    value_objects.py   # TaskStatus 列挙型 + 許可遷移
    exceptions.py      # ドメイン固有例外
  application/
    agents.py          # 共有 agents パッケージからの再エクスポート
    queues.py          # TaskQueue Protocol + QueueMessage スキーマ
    repositories.py    # TaskRepository Protocol
    use_cases.py       # DispatchTask, GetTask, ListTasks, CancelTask など
  infrastructure/
    persistence/       # InMemoryTaskRepository, SqlAlchemyTaskRepository
    queue/             # InMemoryTaskQueue, AzureStorageQueueTaskQueue
    web/               # FastAPI アプリ、ルート、スキーマ、例外ハンドラ
    cli/               # Typer CLI アプリ、ワーカーループ
```

## クイックスタート

```bash
# REST API 起動（デフォルトはインメモリバックエンド）
uv run cloud-agent-web

# ワーカー起動（別ターミナル）
uv run cloud-agent-cli worker

# タスク投入
uv run cloud-agent-cli task dispatch --agent-type echo --payload '{"message": "hello"}'

# 登録済みエージェント一覧
uv run cloud-agent-cli agents
```

## LangGraph エージェントの実行

`langgraph` preset は、LangChain / LangGraph エージェントを
`cloud_agent` タスクパイプラインに統合するためのリファレンス設定です。
統合クラス `LangGraphAgent` で構築され、
[`langchain.agents.create_agent`](https://python.langchain.com/) と
`echo` / `generate_image_tool` のツールビルダ、`init_chat_model` 経由で
Azure 上のチャットモデルを使用します。LLM がユーザーのリクエストに
応じて適切なツールを選択します。ツールを追加したい場合は
`tool_builders` に追加するだけで、エージェントクラスを新規作成する
必要はありません。

### 前提条件

- `AGENTS_LANGGRAPH_MODEL`（デフォルト `azure_ai:gpt-5`）で指定したモデルにアクセスできる
  Azure AI Foundry（または Azure OpenAI）のデプロイメント。
- `DefaultAzureCredential` が解決できるプリンシパル。
  ローカル開発では `az login`、Azure 上では Managed Identity が一般的です。
- 対象プリンシパルが Foundry デプロイメントを呼び出せるロール（例: **Azure AI Developer**）を保有していること。

### 最小構成の `.env`

最も手早く試すならインメモリ構成ですが、API とワーカーは **同じ Python プロセス内**
でないとキュー / リポジトリを共有できないため、別ターミナルで
`cloud-agent-cli worker` と `cloud-agent-cli task dispatch` を実行する場合は
`postgres` + `azure-storage-queue` を使ってください。

```bash
# .env — 別プロセスで動かす構成
CLOUD_AGENT_REPOSITORY_BACKEND=postgres
CLOUD_AGENT_QUEUE_BACKEND=azure-storage-queue
CLOUD_AGENT_AZURE_STORAGE_ACCOUNT_URL=https://<account>.queue.core.windows.net
AGENTS_LANGGRAPH_MODEL=azure_ai:gpt-5

POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=concierge
POSTGRES_PASSWORD=concierge
POSTGRES_DB=concierge
```

### 手順

```bash
# 1. DefaultAzureCredential が token を取得できる状態にする
az login

# 2. 依存サービスを起動（postgres / azure-storage-queue を使うとき）
docker compose up -d postgres

# 3. エージェントが登録されていることを確認
uv run cloud-agent-cli agents
# → ["echo", "langgraph", "github-copilot-echo", "microsoft-agent-framework"]

# 4. ワーカー起動（ターミナル 1）
uv run cloud-agent-cli worker

# 5. タスク投入（ターミナル 2）
uv run cloud-agent-cli task dispatch \
  --agent-type langgraph \
  --payload '{"message": "Hello LangGraph"}'

# 6. 上記で出力された task id で結果を取得
uv run cloud-agent-cli task get <task-id>
```

### payload 仕様

| フィールド | 型 | 必須 | 備考 |
|----------|----|------|------|
| `message` | `string` | 必須 | 非空文字列。LLM へそのまま渡されます。空文字や欠落の場合は `payload.message is required` で失敗します。 |

### 結果の形式

成功時、`result` には以下のオブジェクトが格納されます。

```json
{
  "echo": "Hello LangGraph",
  "reply": "<最終 AI メッセージ>",
  "tool_calls": [
    {"name": "echo", "args": {"text": "Hello LangGraph"}}
  ],
  "model": "azure_ai:gpt-5"
}
```

`reply` はグラフが出力した最後の `AIMessage.content`、`tool_calls` は処理中に
モデルが発行した `(name, args)` のペアです。`model` フィールドは設定した
`AGENTS_LANGGRAPH_MODEL` をそのまま返します。

### カスタマイズ

- `AGENTS_LANGGRAPH_MODEL`: 利用するチャットモデルを変更（例: `azure_ai:gpt-4o-mini`）。
- `AGENTS_LANGGRAPH_SYSTEM_PROMPT`: 組み込みシステムプロンプトを差し替えてコード変更なしで挙動を変更。
- 新しいツールバリエーションを追加する場合は、
  [`concierge/agents/infrastructure/tools/`](https://github.com/ks6088ts-labs/concierge/tree/main/concierge/agents/infrastructure/tools)
  にツールビルダを追加し、
  [`concierge/agents/infrastructure/registry_factory.py`](https://github.com/ks6088ts-labs/concierge/blob/main/concierge/agents/infrastructure/registry_factory.py)
  で `LangGraphAgent(...)` preset をもう 1 つ登録してください。

### トラブルシューティング

| 症状 | 主な原因 |
|------|----------|
| タスクが `QUEUED` のまま | ワーカーが起動していない、または `memory` バックエンドを別プロセス間で利用している。`cloud-agent-cli worker` を起動するか `postgres` + `azure-storage-queue` に切り替える。 |
| `status=failed` で認証関連エラー | `DefaultAzureCredential` がプリンシパルを解決できない。`az login` または Managed Identity を設定する。 |
| `status=failed`, `payload.message is required` | payload に `message` が無いか、空白のみの文字列。 |
| モデルデプロイメントから 403 | プリンシパルに Foundry プロジェクトの **Azure AI Developer** ロールが付与されていない。 |

## タスクライフサイクル

```
QUEUED → RUNNING → SUCCEEDED
                 → FAILED → （リトライ）→ QUEUED
                          → （上限超過）→ DEAD_LETTER
       → CANCELLED
```

---

## 設定 { #configuration }

Cloud Agent の設定はすべて
[`concierge.settings.CloudAgentSettings`](https://github.com/ks6088ts-labs/concierge/blob/main/concierge/settings/cloud_agent.py)
に集約されており、`CLOUD_AGENT_` プレフィックスの環境変数から読み込みます
（[`.env.template`](https://github.com/ks6088ts-labs/concierge/blob/main/.env.template) を参照）。
コード内で `os.environ` を直接参照することはありません。REST API
（`cloud-agent-web`）とディスパッチャ / ワーカー CLI（`cloud-agent-cli`）は
まったく同じ設定オブジェクトを共有します。

### 設定一覧

| 環境変数 | デフォルト | 説明 |
|---------|-----------|------|
| `CLOUD_AGENT_REPOSITORY_BACKEND` | `memory` | タスク永続化バックエンド: `memory` / `postgres` / `azure-postgres` |
| `CLOUD_AGENT_TABLE_NAME` | `cloud_agent_tasks` | SQL バックエンド時のテーブル名 |
| `CLOUD_AGENT_QUEUE_BACKEND` | `memory` | ジョブキューバックエンド: `memory` / `azure-storage-queue` |
| `CLOUD_AGENT_QUEUE_NAME` | `cloud-agent-tasks` | メインキュー名（Azure Storage Queue のリソース名） |
| `CLOUD_AGENT_DLQ_NAME` | `cloud-agent-dlq` | Dead Letter Queue 名（初回利用時に自動作成） |
| `CLOUD_AGENT_AZURE_STORAGE_ACCOUNT_URL` | _(空)_ | `CLOUD_AGENT_QUEUE_BACKEND=azure-storage-queue` のとき**必須**。Queue サービスエンドポイント（例: `https://<account>.queue.core.windows.net`）。認証は Microsoft Entra ID（`DefaultAzureCredential`）のみ、接続文字列 / アカウントキーは**未サポート** |
| `CLOUD_AGENT_VISIBILITY_TIMEOUT_SECONDS` | `60` | デキューしたメッセージが他ワーカーから見えなくなる時間（秒）。エージェントの最悪実行時間より十分長く設定する |
| `CLOUD_AGENT_MAX_RETRIES` | `3` | `DispatchTaskUseCase` のデフォルトリトライ予算。`retry_count > max_retries` で DLQ 行き。API / CLI でディスパッチごとに上書き可能 |
| `CLOUD_AGENT_WORKER_CONCURRENCY` | `1` | 1 ワーカー内の同時実行数（将来拡張用）。現状の実装は逐次処理のため、スケールしたい場合はワーカープロセスを増やす |
| `CLOUD_AGENT_POLL_INTERVAL_SECONDS` | `1.0` | キューが空のときの再ポーリング間隔（秒） |

LangGraph エージェント設定（`AGENTS_LANGGRAPH_MODEL`, `AGENTS_LANGGRAPH_SYSTEM_PROMPT`）は
**共有エージェントランタイム**で管理されます。[共有エージェントランタイム](../agents/index.ja.md) を参照してください。

### リポジトリバックエンドの選択

リポジトリは `Task` 集約を永続化し、`cloud-agent-web` とワーカーの両方から
参照されます。`CLOUD_AGENT_REPOSITORY_BACKEND` で切り替えます。

| 値 | 列挙メンバー | 使いどころ | スキーマ初期化 |
|---|---|---|---|
| `memory`（デフォルト） | `CloudAgentRepositoryBackend.MEMORY` | ローカルの最速試運転。再起動でデータ消失、**プロセスをまたいで共有されない**（API と worker を別プロセスで起動するとそれぞれ別のストアになる） | 不要 |
| `postgres` | `CloudAgentRepositoryBackend.POSTGRES` | Docker Compose のローカル PostgreSQL（`POSTGRES_*`）。`SqlAlchemyTaskRepository` が初回利用時にテーブルを自動作成 | 自動 |
| `azure-postgres` | `CloudAgentRepositoryBackend.AZURE_POSTGRES` | Azure Database for PostgreSQL Flexible Server（`AZURE_*`）。`AZURE_USE_ENTRA_AUTH=true` で Microsoft Entra ID 認証 | 自動 |

!!! tip "`memory` バックエンドとマルチプロセス構成"
    `InMemoryTaskRepository` は Python の dict にデータを保持します。
    `cloud-agent-web` と `cloud-agent-cli worker` を別ターミナルで
    `memory` モード起動すると、2 つの独立したタスクストアになります。
    プロセスを分けるなら `postgres` か `azure-postgres` に切り替えてください。

### キューバックエンドの選択

| 値 | 使いどころ | 必須変数 |
|---|---|---|
| `memory`（デフォルト） | ローカル試運転。`asyncio.Queue` を使う in-process 実装。API と worker が同一 Python プロセス内にいる場合のみ機能 | — |
| `azure-storage-queue` | 本番向けの永続キュー。メインキューと DLQ は起動時に自動作成。認証は `DefaultAzureCredential` による Entra ID のみ | `CLOUD_AGENT_AZURE_STORAGE_ACCOUNT_URL` |

アカウント URL なしで `azure-storage-queue` を選ぶとファクトリが `ValueError` を送出します。
認証は `DefaultAzureCredential` による Microsoft Entra ID のみサポートされ、
呼び出し側プリンシパルにはストレージアカウント上で **Storage Queue Data Contributor**
（または同等のカスタム RBAC）ロールが必要です。
可視性タイムアウトと DLQ ルーティングは
`CLOUD_AGENT_VISIBILITY_TIMEOUT_SECONDS` と `CLOUD_AGENT_DLQ_NAME` で制御します。

### 例: ローカル開発（memory のみ）

```bash
# .env（最小構成）
CLOUD_AGENT_REPOSITORY_BACKEND=memory
CLOUD_AGENT_QUEUE_BACKEND=memory
```

`memory` モードでは API と worker が同一プロセスに居る必要があるため、
ユニットレベルのエンドツーエンド確認用途に限定してください。

### 例: PostgreSQL + Azure Storage Queue

```bash
# .env
CLOUD_AGENT_REPOSITORY_BACKEND=postgres
CLOUD_AGENT_QUEUE_BACKEND=azure-storage-queue
CLOUD_AGENT_AZURE_STORAGE_ACCOUNT_URL=https://<account>.queue.core.windows.net
CLOUD_AGENT_QUEUE_NAME=cloud-agent-tasks
CLOUD_AGENT_DLQ_NAME=cloud-agent-dlq
CLOUD_AGENT_VISIBILITY_TIMEOUT_SECONDS=120
CLOUD_AGENT_MAX_RETRIES=5

# ローカル Postgres 接続情報（Chat / Todo アプリと共有）
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=concierge
POSTGRES_PASSWORD=concierge
POSTGRES_DB=concierge
```

```bash
docker compose up -d postgres
az login                       # DefaultAzureCredential がトークンを取得できる状態に
uv run cloud-agent-web        # ターミナル 1
uv run cloud-agent-cli worker # ターミナル 2
```

起動前に、サインイン済みプリンシパル（またはマネージド ID）に
ストレージアカウントへの **Storage Queue Data Contributor** ロールを付与しておいてください。

### 例: Azure Database for PostgreSQL（Entra ID）+ Azure Storage Queue

```bash
# .env
CLOUD_AGENT_REPOSITORY_BACKEND=azure-postgres
CLOUD_AGENT_QUEUE_BACKEND=azure-storage-queue
CLOUD_AGENT_AZURE_STORAGE_ACCOUNT_URL=https://<account>.queue.core.windows.net

AZURE_DBHOST=<server-name>.postgres.database.azure.com
AZURE_DBNAME=postgres
AZURE_USE_ENTRA_AUTH=true
AZURE_DBUSER=<entra-principal>
```

API / worker 起動前に `az login` などで `DefaultAzureCredential` がトークンを
発行できる状態にしておいてください。同じプリンシパルに、`AZURE_DBUSER` に使う
PostgreSQL ロールに加えてストレージアカウントで **Storage Queue Data Contributor**
ロールも付与しておく必要があります。
