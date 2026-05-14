---
title: Todo CLI Reference
description: Typer commands for the clean architecture Todo app
---

## Commands

```bash
python -m concierge.todo.infrastructure.cli.app task create --title "buy milk" --description "whole milk"
python -m concierge.todo.infrastructure.cli.app task list --status TODO
python -m concierge.todo.infrastructure.cli.app task get <task_id>
python -m concierge.todo.infrastructure.cli.app task update <task_id> --title "buy eggs" --status IN_PROGRESS
python -m concierge.todo.infrastructure.cli.app task complete <task_id>
python -m concierge.todo.infrastructure.cli.app task delete <task_id>
```

## Database Commands

The following commands manage the database schema and are only applicable when
`TODO_REPOSITORY_BACKEND` is set to `postgres` or `azure-postgres`.

```bash
# Initialise schema (CREATE TABLE IF NOT EXISTS)
TODO_REPOSITORY_BACKEND=postgres python -m concierge.todo.infrastructure.cli.app db init

# Check database connectivity (SELECT 1)
TODO_REPOSITORY_BACKEND=postgres python -m concierge.todo.infrastructure.cli.app db ping

# Drop the todo_tasks table (with confirmation prompt)
TODO_REPOSITORY_BACKEND=postgres python -m concierge.todo.infrastructure.cli.app db drop
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `TODO_REPOSITORY_BACKEND` | `memory` | Persistence backend: `memory`, `postgres`, or `azure-postgres` |
| `TODO_TABLE_NAME` | `todo_tasks` | Override the table name used by SQL backends |
