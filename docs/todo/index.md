---
title: Todo App
description: FastAPI and Typer Todo reference application built with clean architecture
---

# Todo App

This repository now includes a small Todo application that demonstrates clean architecture with four layers:

```mermaid
flowchart LR
    infra[Infrastructure\nFastAPI / Typer / InMemory / Settings] --> interfaces[Interfaces\nControllers / Presenters / View Models]
    interfaces --> application[Application\nUse Cases / DTOs / Repository Ports]
    application --> domain[Domain\nTask Entity / Value Objects / Exceptions]
```

## Entry points

```bash
uv run python -m concierge.todo.web_main
uv run python -m concierge.todo.cli_main task create --title "buy milk"
```

The web API exposes `/docs` for OpenAPI and `/healthz` for a lightweight health check.
