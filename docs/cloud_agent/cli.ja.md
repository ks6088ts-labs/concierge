---
title: Cloud Agent CLI リファレンス（日本語）
description: cloud_agent タスクディスパッチとワーカーの CLI コマンド
---

## インストール

`uv sync` を実行すると `cloud-agent-cli` エントリポイントが自動的にインストールされます。

```bash
uv run cloud-agent-cli --help
```

## タスクコマンド

### タスクのディスパッチ

```bash
uv run cloud-agent-cli task dispatch \
  --agent-type echo \
  --payload '{"message": "hello world"}'
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
| `CLOUD_AGENT_AZURE_STORAGE_CONNECTION_STRING` | — | Azure Storage 接続文字列 |
| `CLOUD_AGENT_VISIBILITY_TIMEOUT_SECONDS` | `60` | キュー可視性タイムアウト |
| `CLOUD_AGENT_MAX_RETRIES` | `3` | デフォルト最大リトライ回数 |
| `CLOUD_AGENT_WORKER_CONCURRENCY` | `1` | ワーカー内同時実行数（将来拡張用） |
| `CLOUD_AGENT_POLL_INTERVAL_SECONDS` | `1.0` | キューが空のときのポーリング間隔 |

詳しい解説と構成例は [概要ページの「設定」セクション](index.ja.md#configuration) を参照してください。

## 例: Azure Storage Queue バックエンド

```bash
export CLOUD_AGENT_QUEUE_BACKEND=azure-storage-queue
export CLOUD_AGENT_AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;..."
uv run cloud-agent-cli worker
```
