---
title: 開発ガイド
description: concierge のローカルセットアップ、CLI 実行例、ドキュメント操作、Docker 操作
---

## ローカルセットアップ

開発依存関係をインストールし、環境変数テンプレートをコピーします。

```bash
make install-deps-dev
cp .env.template .env
```

`.env` に Microsoft Foundry project endpoint を設定します。

```dotenv
AZURE_AI_PROJECT_ENDPOINT=https://<resource>.services.ai.azure.com/api/projects/<project>
MLFLOW_TRACKING_URI=http://127.0.0.1:5000
```

Foundry へ接続する前に Azure CLI でサインインします。

```bash
az login
```

## サンプル CLI

利用できる Typer コマンドは help で確認できます。

```bash
uv run python scripts/microsoft_foundry/vanilla.py --help
```

代表的な実行例です。

```bash
uv run python scripts/microsoft_foundry/vanilla.py hello-world \
    --query "Summarize LangChain in one sentence."

uv run python scripts/microsoft_foundry/vanilla.py use-in-agents \
    --query "Explain why observability matters for LLM applications."

uv run python scripts/microsoft_foundry/vanilla.py vector-store-search \
    --query thud --k 1
```

グローバルオプションで observability を有効化できます。

* `--tracing` は Microsoft Foundry / Azure Monitor tracing に LangChain run を送信します。
* `--mlflow` は MLflow の LangChain autologging を有効化します。
* `--verbose` はローカル logger を `DEBUG` にします。

同じグローバルオプションはサービス CLI でも使えます。

```bash
uv run chat-cli --tracing --mlflow --help
uv run cloud-agent-cli --tracing --mlflow --help
uv run todo-cli --tracing --mlflow --help
```

`--mlflow` を使う場合は、別ターミナルでローカル MLflow UI を起動します。

```bash
make mlflow
```

VS Code GitHub Copilot Chat の OpenTelemetry シグナルを Azure Application
Insights へ転送するには、同梱の OTel Collector を起動します（オプトイン。
`.env` に `APPLICATIONINSIGHTS_CONNECTION_STRING` が必要）。

```bash
make copilot-otel-up    # docker-compose の otel-collector サービスを起動
make copilot-otel-logs  # Collector ログを追尾
make copilot-otel-down  # Collector を停止
```

VS Code `settings.json` の設定、KQL での疎通確認、トラブルシューティング
まで含めた手順は
[VS Code Copilot を Application Insights で可視化する](tutorial/appendix-monitor-vscode-copilot.md)
を参照してください。

## 開発コマンド

よく使う操作は Makefile target にまとめています。

```bash
# 利用可能な make target を表示します。
make

# テストを実行します。
make test

# format check、lint、test をまとめて実行します。
make ci-test

# import-linter でクリーンアーキテクチャの依存方向を検証します。
make lint-imports

# docs 依存関係のインストールと site build をまとめて実行します。
make ci-test-docs

# ドキュメントをビルドします。
make docs

# ドキュメントをローカルプレビューします。
make docs-serve
```

Docker image のビルドと実行も Makefile から行えます。

```bash
make docker-build
make docker-run
```

## PostgreSQL (pgvector) CRUD

[`scripts/postgresql/vanilla.py`](https://github.com/ks6088ts-labs/concierge/blob/main/scripts/postgresql/vanilla.py)
の 1 本の Typer CLI で、本リポジトリがサポートする 2 つのターゲットを
カバーします。

* `--target docker` (既定):
  [`compose.yml`](https://github.com/ks6088ts-labs/concierge/blob/main/compose.yml)
  のローカル [pgvector](https://github.com/pgvector/pgvector) PostgreSQL
  サービスを使います。
* `--target azure`: `pgvector` を有効化したマネージドな
  [Azure Database for PostgreSQL Flexible Server](https://learn.microsoft.com/ja-jp/azure/postgresql/flexible-server/overview)
  を使います。既定では Microsoft Entra 認証 (`DefaultAzureCredential` で
  取得したアクセストークンを DB パスワードとして利用) です。

サーバ作成や Entra 構成も含む手順は
[ステップ 3 - PostgreSQL (pgvector) CRUD](tutorial/03-postgres-vector-store.md)
にまとめています。

### 接続情報を設定する

どちらのターゲットも `.env` から設定を読み込みます。
[`.env.template`](https://github.com/ks6088ts-labs/concierge/blob/main/.env.template)
の該当ブロックを `.env` にコピーしてください。

```dotenv
# --target docker (既定値は compose.yml の `postgres` サービスに揃えています)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=concierge
POSTGRES_PASSWORD=concierge
POSTGRES_DB=concierge
POSTGRES_COLLECTION=concierge_docs

# --target azure
AZURE_DBHOST=<server-name>.postgres.database.azure.com
AZURE_DBNAME=postgres
AZURE_DBPORT=5432
AZURE_SSLMODE=require
# Microsoft Entra ID 認証 (推奨)。AZURE_DBUSER には Entra プリンシパル名を指定します。
AZURE_USE_ENTRA_AUTH=true
AZURE_DBUSER=<entra-principal-or-db-user>
# AZURE_USE_ENTRA_AUTH=false のときのみ必須
AZURE_DBPASSWORD=
```

### 接続先を起動する (またはサインインする)

ローカルターゲットでは Compose サービスを起動します。

```bash
docker compose up -d postgres
```

Azure ターゲットでは `DefaultAzureCredential` が ID を参照できるように
サインインしておきます。

```bash
az login
```

### CRUD CLI を実行する

サブコマンドは両ターゲットで完全に共通です。`--target docker` と
`--target azure` を切り替えるだけです。

```bash
# 利用可能な Typer サブコマンドを確認します。
uv run python scripts/postgresql/vanilla.py --help

# テーブル作成 → サンプル一括投入 → 類似検索の順に試します。
uv run python scripts/postgresql/vanilla.py create-table
uv run python scripts/postgresql/vanilla.py bulk-create
uv run python scripts/postgresql/vanilla.py search --query "fruit"

# Azure Flexible Server に対しても同じ流れで実行できます。
uv run python scripts/postgresql/vanilla.py --target azure create-table
uv run python scripts/postgresql/vanilla.py --target azure bulk-create
uv run python scripts/postgresql/vanilla.py --target azure search --query "fruit"

# id 指定で取得・更新・削除します。
uv run python scripts/postgresql/vanilla.py read --id apple
uv run python scripts/postgresql/vanilla.py update --id apple \
    --text "Apples, oranges, and bananas are fruits."
uv run python scripts/postgresql/vanilla.py delete --id apple

# 検証が終わったらテーブルを削除します。
uv run python scripts/postgresql/vanilla.py drop-table
```

`--fake-embeddings` を付けると Microsoft Foundry を呼ばずに
`DeterministicFakeEmbedding` で実行できます。両ターゲットで使えるフラグで、
`--target docker` ならローカル完結のオフライン反復、
`--target azure` なら Foundry 埋め込みデプロイがまだ無い段階で Azure 接続
パスを通しで確認するのに便利です。

```bash
uv run python scripts/postgresql/vanilla.py --fake-embeddings create-table --overwrite
uv run python scripts/postgresql/vanilla.py --fake-embeddings bulk-create
uv run python scripts/postgresql/vanilla.py --fake-embeddings search \
    --query "fruit"

# Azure ターゲットに対しても同じフラグが使えます。
uv run python scripts/postgresql/vanilla.py --target azure --fake-embeddings create-table --overwrite
```

### ローカル DB の確認・停止

```bash
# PostgreSQL のログを tail します。
docker compose logs -f postgres

# コンテナ内で psql を起動します。
docker compose exec postgres psql -U concierge -d concierge

# サービスを停止します (ボリュームは保持されます)。
docker compose stop postgres
docker compose rm -f postgres
```

## GitHub Pages

[github-pages workflow](https://github.com/ks6088ts-labs/concierge/actions/workflows/github-pages.yaml) は、`main` ブランチから `mkdocs gh-deploy --force` で MkDocs site をデプロイします。

* [公開ドキュメント](https://ks6088ts-labs.github.io/concierge/)
* [日本語版ドキュメント](https://ks6088ts-labs.github.io/concierge/ja/)
* [ハンズオンチュートリアル](https://ks6088ts-labs.github.io/concierge/tutorial/)
