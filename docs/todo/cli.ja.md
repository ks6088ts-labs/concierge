---
title: Todo CLI リファレンス
description: クリーンアーキテクチャ Todo アプリの Typer コマンド
---

## コマンド

```bash
python -m concierge.todo.infrastructure.cli.app task create --title "buy milk" --description "whole milk"
python -m concierge.todo.infrastructure.cli.app task list --status TODO
python -m concierge.todo.infrastructure.cli.app task get <task_id>
python -m concierge.todo.infrastructure.cli.app task update <task_id> --title "buy eggs" --status IN_PROGRESS
python -m concierge.todo.infrastructure.cli.app task complete <task_id>
python -m concierge.todo.infrastructure.cli.app task delete <task_id>
```

## データベースコマンド

以下のコマンドはデータベーススキーマを管理します。`TODO_REPOSITORY_BACKEND` が `postgres` または `azure-postgres` の場合のみ有効です。

```bash
# スキーマ初期化（CREATE TABLE IF NOT EXISTS）
TODO_REPOSITORY_BACKEND=postgres python -m concierge.todo.infrastructure.cli.app db init

# データベース接続確認（SELECT 1）
TODO_REPOSITORY_BACKEND=postgres python -m concierge.todo.infrastructure.cli.app db ping

# todo_tasks テーブル削除（確認プロンプトあり）
TODO_REPOSITORY_BACKEND=postgres python -m concierge.todo.infrastructure.cli.app db drop
```

## 環境変数

| 変数 | デフォルト | 説明 |
|---|---|---|
| `TODO_REPOSITORY_BACKEND` | `memory` | 永続化バックエンド: `memory`、`postgres`、または `azure-postgres` |
| `TODO_TABLE_NAME` | `todo_tasks` | SQL バックエンドで使用するテーブル名のオーバーライド |
