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
