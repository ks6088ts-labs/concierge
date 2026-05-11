---
title: Todo CLI
description: Typer CLI usage for the Todo application
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

The CLI calls the same use cases as the FastAPI layer.
