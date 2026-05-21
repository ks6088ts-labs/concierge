---
title: Cloud Agent CLI リファレンス（日本語）
description: cloud_agent タスクディスパッチとワーカーの CLI コマンド
---

## インストール

`uv sync` を実行すると `cloud-agent-cli` エントリポイントが自動的にインストールされます。

```bash
uv run cloud-agent-cli --help
```

## observability のグローバルオプション

- `--tracing`: 共有 tracing 状態を有効化（tracer 名: `concierge-cloud-agent`）
- `--mlflow`: `mlflow.langchain.autolog()` の初期化を有効化
- `--verbose`: DEBUG ログを有効化

## タスクコマンド

### タスクのディスパッチ

組み込みエージェント（`echo` / `langgraph-echo` / `github-copilot-echo` / `microsoft-agent-framework-echo`）は同じ payload 仕様で、
非空文字列の `message` が必須です。

```bash
uv run cloud-agent-cli task dispatch \
  --agent-type echo \
  --payload '{"message": "hello world"}'
```

### LangGraph エコータスクのディスパッチ

```bash
uv run cloud-agent-cli task dispatch \
  --agent-type langgraph-echo \
  --payload '{"message": "Hello LangGraph"}'
```

ワーカーがタスクを処理し、結果を保存します。結果を取得するには:

```bash
uv run cloud-agent-cli task get <uuid>
```

成功時の結果の例:

```json
{
  "echo": "Hello LangGraph",
  "reply": "Hello LangGraph",
  "tool_calls": [
    {"name": "echo", "args": {"text": "Hello LangGraph"}}
  ]
}
```

オプション:

| フラグ | 必須 | 説明 |
|--------|------|------|
| `--agent-type` | 必須 | 登録済みエージェント識別子 |
| `--payload` | 省略可 | JSON 文字列（デフォルト `{}`） |
| `--max-retries` | 省略可 | 最大リトライ回数を上書き |

### タスク詳細取得

```bash
uv run cloud-agent-cli task get <uuid>
```

### タスク一覧

```bash
# 全件取得
uv run cloud-agent-cli task list

# ステータスでフィルタ
uv run cloud-agent-cli task list --status QUEUED

# エージェントタイプでフィルタ
uv run cloud-agent-cli task list --agent-type echo

# ページング
uv run cloud-agent-cli task list --limit 10 --offset 20
```

### タスクキャンセル

```bash
uv run cloud-agent-cli task cancel <uuid>
```

## ワーカーコマンド

```bash
# 無制限に実行
uv run cloud-agent-cli worker

# 指定回数だけ実行（テスト用途）
uv run cloud-agent-cli worker --max-iterations 5
```

ワーカーは `SIGINT` / `SIGTERM` を受け取るとグレースフルシャットダウンします。
処理中のタスクを完了させてから停止します。

## エージェント一覧コマンド

```bash
uv run cloud-agent-cli agents
```

## 設定

すべての設定は環境変数（または `.env` ファイル）で制御します。

| 環境変数 | デフォルト | 説明 |
|---------|-----------|------|
| `CLOUD_AGENT_REPOSITORY_BACKEND` | `memory` | `memory` / `postgres` / `azure-postgres` |
| `CLOUD_AGENT_TABLE_NAME` | `cloud_agent_tasks` | SQL テーブル名 |
| `CLOUD_AGENT_QUEUE_BACKEND` | `memory` | `memory` / `azure-storage-queue` |
| `CLOUD_AGENT_QUEUE_NAME` | `cloud-agent-tasks` | メインキュー名 |
| `CLOUD_AGENT_DLQ_NAME` | `cloud-agent-dlq` | Dead Letter キュー名 |
| `CLOUD_AGENT_AZURE_STORAGE_ACCOUNT_URL` | — | Azure Storage Queue のエンドポイント（Entra ID 認証 / `DefaultAzureCredential`） |
| `CLOUD_AGENT_VISIBILITY_TIMEOUT_SECONDS` | `60` | キュー可視性タイムアウト |
| `CLOUD_AGENT_MAX_RETRIES` | `3` | デフォルト最大リトライ回数 |
| `CLOUD_AGENT_WORKER_CONCURRENCY` | `1` | ワーカー内同時実行数（将来拡張用） |
| `CLOUD_AGENT_POLL_INTERVAL_SECONDS` | `1.0` | キューが空のときのポーリング間隔 |
| `AGENTS_LANGGRAPH_MODEL` | `azure_ai:gpt-5` | LangGraph エージェントで使う `init_chat_model` のモデル文字列 |
| `AGENTS_LANGGRAPH_SYSTEM_PROMPT` | _(組み込み)_ | LangGraph エージェントのシステムプロンプト |
| `AGENTS_GITHUB_COPILOT_MODEL` | `gpt-5-mini` | `github-copilot-echo` のモデル名 |
| `AGENTS_GITHUB_COPILOT_SYSTEM_PROMPT` | _(組み込み)_ | `github-copilot-echo` のシステムプロンプト |
| `AGENTS_MICROSOFT_AGENT_FRAMEWORK_MODEL` | `gpt-5` | `microsoft-agent-framework-echo` のモデル文字列 |
| `AGENTS_MICROSOFT_AGENT_FRAMEWORK_SYSTEM_PROMPT` | _(組み込み)_ | `microsoft-agent-framework-echo` のシステムプロンプト |

詳しい解説と構成例は [概要ページの「設定」セクション](index.ja.md#configuration) を参照してください。

## 例: Azure Storage Queue バックエンド

認証は `DefaultAzureCredential` を介した Microsoft Entra ID のみサポートします。
サインイン済みプリンシパル（またはマネージド ID）に
ストレージアカウントで **Storage Queue Data Contributor** ロールを付与してください。

```bash
export CLOUD_AGENT_QUEUE_BACKEND=azure-storage-queue
export CLOUD_AGENT_AZURE_STORAGE_ACCOUNT_URL="https://<account>.queue.core.windows.net"
az login
uv run cloud-agent-cli worker
```
