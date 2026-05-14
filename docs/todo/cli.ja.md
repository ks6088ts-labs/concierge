---
title: Todo CLI リファレンス
description: クリーンアーキテクチャ Todo アプリの Typer コマンド
---

## コマンド

```bash
uv run todo-cli task create --title "buy milk" --description "whole milk"
uv run todo-cli task list --status TODO
uv run todo-cli task get <task_id>
uv run todo-cli task update <task_id> --title "buy eggs" --status IN_PROGRESS
uv run todo-cli task complete <task_id>
uv run todo-cli task delete <task_id>
```

## データベースコマンド

以下のコマンドはデータベーススキーマを管理します。`.env` で `TODO_REPOSITORY_BACKEND` を `postgres` または `azure-postgres` に設定した場合のみ有効です。

```bash
# スキーマ初期化（CREATE TABLE IF NOT EXISTS）
uv run todo-cli db init

# データベース接続確認（SELECT 1）
uv run todo-cli db ping

# todo_tasks テーブル削除（確認プロンプトあり）
uv run todo-cli db drop
```

## 環境変数

以下の変数は `concierge.settings.TodoSettings` が読み込みます。Todo
アプリ用の環境変数アクセスはすべてこのクラスに集約されています。

| 変数 | デフォルト | 型 | 説明 |
|---|---|---|---|
| `TODO_REPOSITORY_BACKEND` | `memory` | `TodoRepositoryBackend` 列挙型（`memory`、`postgres`、`azure-postgres`） | 永続化バックエンド。未定義の値は起動時に拒否されます。 |
| `TODO_TABLE_NAME` | `todo_tasks` | 文字列 | SQL バックエンドで使用するテーブル名のオーバーライド |
