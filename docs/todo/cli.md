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
