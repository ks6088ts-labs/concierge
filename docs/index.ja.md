---
title: concierge
description: Microsoft Foundry、LangChain、LangGraph のハンズオンドキュメント
---

## concierge とは

`concierge` は、[Microsoft Foundry](https://learn.microsoft.com/ja-jp/azure/foundry/)
上のモデルを [LangChain](https://docs.langchain.com/) /
[LangGraph](https://docs.langchain.com/oss/python/langgraph/quickstart)
から扱う LLM アプリケーション構築用の Python ハンズオンリポジトリです。
読みどころは大きく 2 つあります。

| 構成 | 完全ローカルで動く？ | 学べること |
| :--- | :---: | :--- |
| [Todo アプリ (クリーンアーキテクチャ)](todo/index.md) | はい | FastAPI + Typer + クリーンアーキテクチャの小さな参考実装 |
| [ハンズオンチュートリアル](tutorial/index.md) | 一部 | Foundry チャット / 埋め込み、観測性、pgvector、LangGraph エージェント |

## どこから読むか

目的にいちばん近いところから始めてください。各経路は次のステップに繋がっ
ているので、必要なところまで進めばOKです。

=== "まずコードを読みたい"

    [Todo アプリ概要](todo/index.md) から始めます。`uv run todo-web`
    の 1 コマンドで起動し、Azure 認証も不要です。FastAPI / Typer /
    リポジトリ層の繋がりを最小構成で確認できます。

=== "Foundry をとにかく呼んでみたい"

    [ステップ 1 - Microsoft Foundry + LangChain](tutorial/01-foundry-langchain.md)
    に進みます。Typer CLI から Foundry プロジェクトに対するチャット
    completion を 5 分以内に実行できます。

=== "LLM トレースをデバッグしたい"

    [ステップ 2 - 観測性 (トレース & MLflow)](tutorial/02-observability.md)
    を読みます。LangChain 実行を Azure Monitor に送り、ローカル MLflow
    UI で閲覧する方法をスクリーンショット付きで紹介しています。

=== "永続ベクトルストアを使いたい"

    [ステップ 3 - PostgreSQL (pgvector) CRUD](tutorial/03-postgres-vector-store.md)
    を読みます。1 本の Typer CLI で Docker Compose 上の pgvector と
    Azure Database for PostgreSQL Flexible Server の両方を切り替えて使えます。

=== "エージェントを動かしてみたい"

    [ステップ 4 - LangGraph Todo Agent CLI](tutorial/04-langgraph-todo-agent.md)
    を読みます。LangGraph エージェントがツール経由で Todo Web API を操作
    し、ステップ 1～3 の要素をひとまとめにします。

## クイックリファレンス

* [開発ガイド](development.md): 環境構築、`make` ターゲット、Docker 操作。
* [チュートリアル概要](tutorial/index.md): 推奨される読み進め方。
* [Appendix - 外部参考リンク](tutorial/appendix.md): Microsoft Learn /
  上流ドキュメントへのリンク集。
