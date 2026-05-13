---
title: concierge
description: Microsoft Foundry、LangChain、LangGraph のハンズオンドキュメント
---

## 概要

`concierge` は、Microsoft Foundry 上のモデルを LangChain / LangGraph 系のワークフローから扱うための Python ハンズオンリポジトリです。現在のコードベースには、chat、agent、embedding、vector store search、Azure Monitor tracing、ローカル MLflow observability を試す Typer CLI が含まれています。

現在の Foundry と LangChain のサンプルがどの GitHub Issue を背景に追加されたのかを理解するには、まず [ハンズオンチュートリアル](tutorial/index.md) から読み進めてください。

ローカルセットアップ、CLI 実行例、ドキュメント操作、Docker 操作は [開発ガイド](development.md) にまとめています。

## 主な入口

* [Step 1 - Microsoft Foundry + LangChain](tutorial/01-foundry-langchain.md)
* [Step 2 - tracing と MLflow による observability](tutorial/02-observability.md)
* [Step 3 - Clean Architecture と IaC の次のステップ](tutorial/03-next-steps.md)
* [Step 4 - PostgreSQL (pgvector) CRUD](tutorial/04-postgres-vector-store.md)
* [Step 5 - Azure Database for PostgreSQL (pgvector) CRUD](tutorial/05-azure-postgres-vector-store.md)
* [開発ガイド](development.md)
* [Appendix - References](tutorial/appendix.md)
