---
title: Todo App (Clean Architecture)
description: FastAPI + Typer Todo sample with clean architecture layers
---

## Overview

This Todo sample demonstrates a minimal clean architecture implementation in this repository.

```mermaid
flowchart LR
    Web[FastAPI Routes] --> App[Application Use Cases]
    CLI[Typer Commands] --> App
    App --> Domain[Domain Entities / Value Objects]
    Web --> Repo[InMemory Repository]
    CLI --> Repo
    Repo --> Domain
```

## Quickstart

```bash
uv run uvicorn concierge.todo.infrastructure.web.app:create_app --factory --host 0.0.0.0 --port 8000
```

```bash
uv run python -m concierge.todo.infrastructure.cli.app task create --title "buy milk"
```
