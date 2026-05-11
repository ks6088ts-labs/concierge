---
title: Todo アプリ
description: クリーンアーキテクチャで構成した FastAPI / Typer ベースの Todo サンプル
---

# Todo アプリ

このリポジトリには、4 層のクリーンアーキテクチャを示す小さな Todo アプリを追加しています。

```mermaid
flowchart LR
    infra[Infrastructure\nFastAPI / Typer / InMemory / Settings] --> interfaces[Interfaces\nControllers / Presenters / View Models]
    interfaces --> application[Application\nUse Cases / DTOs / Repository Ports]
    application --> domain[Domain\nTask Entity / Value Objects / Exceptions]
```

## エントリポイント

```bash
uv run python -m concierge.todo.web_main
uv run python -m concierge.todo.cli_main task create --title "buy milk"
```

Web API では `/docs` で OpenAPI、`/healthz` でヘルスチェックを利用できます。
