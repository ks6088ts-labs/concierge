---
title: Knowledge CLI リファレンス（日本語）
description: pgvector ベースのナレッジストアに Markdown を取り込む Typer CLI
---

## インストール

`knowledge-cli` は `uv sync` で自動インストールされ、`pyproject.toml` の
`[project.scripts]` に登録されています。

```bash
uv run knowledge-cli --help
```

CLI のサブコマンドグループは 2 つあります。

* `ingest` — 書き込み系: `run` / `stats` / `drop`
* `search` — 読み取り系: `run`

## observability のグローバルオプション

トップレベルのコールバックで処理されるため、**サブコマンドより前**に渡す必要があります。

| フラグ | ショート | 説明 |
|--------|---------|------|
| `--tracing` | `-t` | 共有 tracing 状態を有効化（tracer 名: `concierge`） |
| `--mlflow`  | `-m` | `mlflow.langchain.autolog()` の初期化を有効化 |
| `--verbose` | `-v` | DEBUG ログを有効化 |

例:

```bash
uv run knowledge-cli -t -v -m ingest run --collection demo_md docs
```

呼び出しごとに `load_dotenv()` で `.env` が自動的に読み込まれます。

!!! note "MLflow のトレースグルーピング"
    `--mlflow` を付けると、`ingest run` 全体が MLflow の親スパン
    (`knowledge.ingest.run`) でラップされます。これにより
    `mlflow.openai.autolog()` が捕捉するチャンクごとの embeddings
    HTTP コールが、MLflow UI 上で個別のルートトレースにならず、
    CLI 実行ごとに 1 つのトレースに集約されます。

## コマンド

### `ingest run` — Markdown をインデックス

```bash
uv run knowledge-cli ingest run [OPTIONS] PATHS...
```

`PATHS` に指定したディレクトリ配下の `*.md` をすべて再帰的に収集（ファイル
パスの直接指定も可）し、`RecursiveCharacterTextSplitter`
（`KNOWLEDGE_CHUNK_SIZE` / `KNOWLEDGE_CHUNK_OVERLAP`）で分割、各チャンクを
埋め込み、pgvector テーブルへ upsert します。テーブルが存在しない場合は
自動で作成されます。

| フラグ | デフォルト | 説明 |
|--------|-----------|------|
| `--collection` | `KNOWLEDGE_DEFAULT_COLLECTION` | テーブル名（`^[A-Za-z0-9_]+$`） |
| `--target` | `docker` | `docker`（`POSTGRES_*`）または `azure`（`AZURE_*`）。大文字小文字を区別しません。 |

成功時の出力:

```
ingest completed: files=<N> chunks=<M> records=<M>
```

`records` は upsert 後のコレクションの総行数（今回の挿入数ではない）です。
`ChunkId`（`{collection}:{source}:{chunk_index}:{sha256[:12]}`）が決定論的
なので、同一内容を再 ingest しても `records` は増えません。

### `ingest stats` — コレクション件数

```bash
uv run knowledge-cli ingest stats [--collection NAME] [--target docker|azure]
```

現在の行数を表示します。テーブル未作成時は例外ではなく `0` を返すので、
初回 ingest 前に実行しても安全です。

```
collection=demo_md records=42
```

### `ingest drop` — コレクション削除

```bash
uv run knowledge-cli ingest drop [--collection NAME] [--target docker|azure] [--yes]
```

`PGEngine.drop_table` でテーブルを削除します。確認プロンプトが出るため、
CI など非対話実行では `--yes` / `-y` を付与してください。

```
dropped collection=demo_md
```

### `search run` — コレクションを検索

```bash
uv run knowledge-cli search run [OPTIONS] QUERY
```

Ingest 時と同じ `create_embeddings()` factory で `QUERY` を埋め込み、
対象 pgvector コレクションに対して `similarity_search` を実行します。
テーブルは事前に作成されている必要があります（テーブルを作るのは
`ingest run` のみ）。

| フラグ | デフォルト | 説明 |
|--------|-----------|------|
| `--collection` | `KNOWLEDGE_DEFAULT_COLLECTION` | 検索対象テーブル（`^[A-Za-z0-9_]+$`） |
| `--target` | `docker` | `docker`（`POSTGRES_*`）または `azure`（`AZURE_*`）。大文字小文字を区別しません。 |
| `--k` / `-k` | `4` | 返す件数（`>= 1`） |
| `--snippet` | `200` | 出力するチャンク本文の最大文字数。`0` で全文出力。切り詰められた場合は末尾に `...` が付きます。 |
| `--json` | _(off)_ | `{id, content, metadata}` の生 JSON 配列を出力。他ツールへのパイプ用途。 |

人間が読む用の出力例:

```
collection=demo_md query='vector store' hits=2
[1] source=docs/tutorial/03-postgres-vector-store.md chunk=0
pgvector は PostgreSQL 拡張で、ベクターを保存・検索できる...
[2] source=docs/knowledge/index.md chunk=2
`concierge.knowledge` は独立したバウンデッドコンテキストで...
```

JSON 出力（`--json`）:

```json
[
  {
    "id": "demo_md:docs/tutorial/03-postgres-vector-store.md:0:abc123def456",
    "content": "pgvector is a PostgreSQL extension...",
    "metadata": {
      "source": "docs/tutorial/03-postgres-vector-store.md",
      "collection": "demo_md",
      "chunk_index": 0,
      "content_sha256": "...",
      "ingested_at": "2026-05-24T12:34:56+00:00"
    }
  }
]
```

ヒットが 0 件だった場合は exit code `0` のまま以下を出力します。

```
no results for collection=demo_md query='nothing matches'
```

## 環境変数

完全な一覧は
[Knowledge Indexer 概要](index.ja.md#設定) を参照してください。
スモークテスト時によく使うもの:

| 環境変数 | スモークテスト値 | 補足 |
|----------|-----------------|------|
| `KNOWLEDGE_EMBEDDING_PROVIDER` | `fake` | Foundry を呼ばず決定論的なベクターを生成 |
| `KNOWLEDGE_DEFAULT_COLLECTION` | `demo_md` | 全コマンドで `--collection` を省略可能になる |
| `KNOWLEDGE_CHUNK_SIZE` / `KNOWLEDGE_CHUNK_OVERLAP` | `1000` / `200` | 日本語/英語の散文には妥当 |
| `AZURE_AI_PROJECT_ENDPOINT` | – | `KNOWLEDGE_EMBEDDING_PROVIDER=foundry` のときに必須 |

!!! warning "`fake` は配線確認専用 — 実検索は `foundry` に切替"
    `fake`（`DeterministicFakeEmbedding`）は意味を持たないため、`fake` で
    構築したコレクションは無関係な検索結果を返します（RAG/realtime 側は
    「関連情報なし」と報告）。実検索では `KNOWLEDGE_EMBEDDING_PROVIDER=foundry`
    にして**入れ直して**ください（`ingest drop` → `ingest run`）。詳細は
    [トラブルシューティング](index.ja.md#トラブルシューティング)を参照。

## エンドツーエンドの最小手順

クローン直後からコレクションが投入され、件数まで確認できる最短手順:

```bash
# 1. pgvector を起動し、Azure 不要な fake embeddings を使用
docker compose up -d postgres
export KNOWLEDGE_EMBEDDING_PROVIDER=fake

# 2. このリポジトリの docs/ をインジェスト
uv run knowledge-cli ingest run --collection demo_md docs

# 3. 件数を確認
uv run knowledge-cli ingest stats --collection demo_md

# 4. （任意）後片付け
uv run knowledge-cli ingest drop --collection demo_md --yes
```

Azure 構成で動かす場合は、手順 1 を `az login` と
[ステップ 3 – PostgreSQL (pgvector) CRUD](../tutorial/03-postgres-vector-store.ja.md)
で示している `AZURE_*` 環境変数の設定に置き換え、各コマンドに `--target azure`
を付け足してください。
