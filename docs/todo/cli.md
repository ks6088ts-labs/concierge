---
title: Todo CLI Reference
description: Typer commands for the clean architecture Todo app
---

## Commands

```bash
uv run todo-cli task create --title "buy milk" --description "whole milk"
uv run todo-cli task list --status TODO
uv run todo-cli task get <task_id>
uv run todo-cli task update <task_id> --title "buy eggs" --status IN_PROGRESS
uv run todo-cli task complete <task_id>
uv run todo-cli task delete <task_id>
```

## Database Commands

The following commands manage the database schema and are only applicable when
`TODO_REPOSITORY_BACKEND` is set to `postgres` or `azure-postgres` in `.env`.

```bash
# Initialise schema (CREATE TABLE IF NOT EXISTS)
uv run todo-cli db init

# Check database connectivity (SELECT 1)
uv run todo-cli db ping

# Drop the todo_tasks table (with confirmation prompt)
uv run todo-cli db drop
```

## Environment Variables

The variables below are loaded by `concierge.settings.TodoSettings`; all
Todo-specific environment access is funnelled through that single class.

| Variable | Default | Type | Description |
|---|---|---|---|
| `TODO_REPOSITORY_BACKEND` | `memory` | `TodoRepositoryBackend` enum (`memory`, `postgres`, `azure-postgres`) | Persistence backend. Invalid values are rejected at startup. |
| `TODO_TABLE_NAME` | `todo_tasks` | string | Override the table name used by SQL backends |
