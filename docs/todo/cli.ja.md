---
title: Todo CLI
description: Todo アプリ用 Typer CLI の使い方
---

# Todo CLI

```bash
uv run python -m concierge.todo.cli_main task create --title "buy milk"
uv run python -m concierge.todo.cli_main task list --status TODO
uv run python -m concierge.todo.cli_main task get <task_id>
uv run python -m concierge.todo.cli_main task update <task_id> --status IN_PROGRESS
uv run python -m concierge.todo.cli_main task complete <task_id>
uv run python -m concierge.todo.cli_main task delete <task_id>
```

CLI は FastAPI と同じユースケースを呼び出します。
