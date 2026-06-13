# ハンズオンチュートリアル

ようこそ。本ガイドは **concierge** リポジトリの現在の実装を段階的に理解
するハンズオンです。各ステップで「なぜ」「何を」変えるのかを追体験しな
がら手を動かせる構成にしています。

## このチュートリアルの目的

このリポジトリは [Microsoft Foundry](https://learn.microsoft.com/ja-jp/azure/foundry/)
上で [LangChain](https://docs.langchain.com/) / [LangGraph](https://docs.langchain.com/oss/python/langgraph/quickstart)
を使った LLM アプリケーションを始めるためのテンプレートです。完成したコード
を単に読むよりも、ステップごとに組み上げていくことで設計意図が見えるよう
にしています。

## 推奨される読み進め方

このチュートリアルは **上から順番に** 読むのが最短経路です。各ステップは
直前のステップだけに依存し、単独で動作確認できます。

| ステップ | テーマ | 何を足すか | Azure が必要？ |
| :--- | :--- | :--- | :---: |
| [1](01-foundry-langchain.md) | Microsoft Foundry + LangChain | Foundry モデルを呼ぶ Typer CLI | 必要 |
| [2](02-observability.md) | 観測性 (トレース & MLflow) | LangChain 実行を Azure Monitor とローカル MLflow UI に流す | 必要 / 一部のみ[^1] |
| [3](03-postgres-vector-store.md) | PostgreSQL (pgvector) CRUD | 永続ベクトルストア（ローカル / Azure 両対応） | 任意[^2] |
| [4](04-langgraph-todo-agent.md) | LangGraph Todo Agent CLI | Todo Web API をツール経由で操作する ReAct エージェント | 必要 |
| [5](05-mlflow-genai-evaluation.md) | MLflow GenAI 評価 | ヒューリスティック / LLM-judge / カスタム Scorer でエージェント出力品質を評価・比較する | 一部のみ[^3] |

[^1]: MLflow はローカル完結で、Azure Monitor 側のみ Foundry のトレーシング
      機能を有効化する必要があります。
[^2]: ステップ 3 には Foundry を呼ばない `--fake-embeddings` フラグがあり、
      既定の `--target docker` はローカル Docker Compose pgvector を使います。
[^3]: ステップ 5a〜5c と 5e はローカル完結です。Azure 資格情報とデプロイ済み
      モデルが必要なのは `judge` サブコマンド（ステップ 5d）のみです。

!!! tip "まずローカルで動かしてみたい場合"
    [Todo アプリ (クリーンアーキテクチャ)](../todo/index.md) のセクション
    は Azure 認証なしで起動でき、FastAPI / Typer / リポジトリ層の関係を
    すぐ確認できます。

## 全体アーキテクチャ

```mermaid
flowchart LR
    User([開発者])
    CLI["Typer CLI<br/>scripts/microsoft_foundry/vanilla.py"]
    Settings["Pydantic 設定<br/>concierge/settings/*"]
    LC["LangChain / LangGraph"]
    Foundry[("Microsoft Foundry<br/>プロジェクトエンドポイント")]
    Models["Foundry 上のモデル<br/>gpt-5, text-embedding-3-small, ..."]
    Tracer["AzureAIOpenTelemetryTracer"]
    Monitor[("Azure Monitor")]
    MLflow[("MLflow Tracking<br/>http://127.0.0.1:5000")]

    User --> CLI
    CLI --> Settings
    CLI --> LC
    LC -->|"チャット / 埋め込み / エージェント"| Foundry
    Foundry --> Models
    LC -.->|"--tracing"| Tracer --> Monitor
    LC -.->|"--mlflow autolog"| MLflow
```

## 前提条件

以下のツールを事前にインストール・設定してください。バージョンは本リポジトリ
の [`pyproject.toml`](https://github.com/ks6088ts-labs/concierge/blob/main/pyproject.toml)
と [`Makefile`](https://github.com/ks6088ts-labs/concierge/blob/main/Makefile)
に揃えています。

- [Python 3.10 以上](https://www.python.org/downloads/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/): 依存解決と
  仮想環境を `make` ターゲットから一元管理するために利用します。
- [GNU Make](https://www.gnu.org/software/make/): `uv` コマンドを包む薄い
  ラッパーです。
- [Microsoft Foundry](https://ai.azure.com/) を利用可能な Azure サブスクリプ
  ション。チャット / 埋め込みモデルがデプロイ済みであること。例ではコード
  上の既定デプロイ名 (`gpt-5` と `text-embedding-3-small`) を使いますが、
  自分のプロジェクトで利用可能なデプロイ名に置き換えてください。
- [Azure CLI](https://learn.microsoft.com/ja-jp/cli/azure/install-azure-cli)
  にサインイン済み (`az login`) であること。`DefaultAzureCredential` が
  認証情報として参照します。

!!! tip "なぜ `DefaultAzureCredential` を使うのか"
    本リポジトリの CLI は
    [`DefaultAzureCredential`](https://learn.microsoft.com/ja-jp/python/api/azure-identity/azure.identity.defaultazurecredential)
    で認証します。`az login` / マネージド ID / 環境変数 / 開発者資格情報を
    自動的にフォールバックして使うため、API キーを自分で管理する必要があり
    ません。

## 各ステップの読み方

すべてのステップは同じ構造で記述しています。

1. **ゴール**: そのステップで何が手に入るか。
2. **背景**: なぜ必要なのか / なぜこの設計なのか。
3. **手順**: 実行できるコマンドと、理解に必要なコード抜粋。
4. **動作確認**: 期待される出力。
5. **トラブルシューティング**: よくあるつまずきと対処。

それでは [ステップ 1 - Microsoft Foundry + LangChain](01-foundry-langchain.md)
から始めましょう。
