---
title: Agents CLI リファレンス（日本語）
description: 共有エージェントランタイムを単体で動作確認するための CLI
---

## インストール

`uv sync` を実行すると `agents-cli` エントリポイントが自動的にインストールされます。

```bash
uv run agents-cli --help
```

`agents-cli` は共有レジストリの `Agent.handle(AgentRequest)` を直接呼び出します。
`cloud_agent` のタスクキューや `chat` の会話フローを立ち上げずに、
登録済みエージェントを単体で動作確認できます。

## observability のグローバルオプション

- `--tracing`: 共有 tracing 状態を有効化（tracer 名: `concierge-agents`）
- `--mlflow`: `mlflow.langchain.autolog()` の初期化を有効化
- `--verbose`: DEBUG ログを有効化

`bootstrap_from_env` により環境変数（`CONCIERGE_TRACING_ENABLED` /
`CONCIERGE_MLFLOW_ENABLED`）が先に適用され、その後でコマンドラインの
フラグが上書きします。

## コマンド

### 登録済みエージェントの一覧

```bash
uv run agents-cli list
```

出力例:

```json
["echo", "langgraph", "github-copilot-sdk", "microsoft-agent-framework", "foundry-agent-service"]
```

### 設定済み Knowledge retrieval ツール一覧

```bash
uv run agents-cli knowledge list
```

用途: `AGENTS_KNOWLEDGE__*` の設定ミスを CI/CD で事前検知する dry-run。
`name` / `collection` / `description` / `top_k` / `max_chars` を含む
JSON 配列を標準出力に出します。

出力例:

```json
[{"name":"search_docs","collection":"knowledge_default","description":"Search docs.","top_k":4,"max_chars":1200}]
```

終了コードは成功時 `0`、設定バリデーション失敗時 `1` です。

### エージェント実行

`Agent.handle()` を呼び出し、`AgentResponse` を JSON として出力します。
`status == "succeeded"` の場合は終了コード `0`、それ以外は `1` です。

```bash
# JSON ペイロードを明示的に指定
uv run agents-cli invoke \
  --agent-type echo \
  --payload '{"message": "hello world"}'

# ショートカット: --message は {"message": value} を --payload にマージ
uv run agents-cli invoke --agent-type echo --message "hello world"

# AgentRequest.context にメタ情報を渡す
uv run agents-cli invoke \
  --agent-type echo \
  --message "hello" \
  --context '{"task_id": "00000000-0000-0000-0000-000000000001"}'
```

組み込みエージェント（`echo` / `langgraph` / `github-copilot-sdk` / `microsoft-agent-framework` / `foundry-agent-service`）は
`payload.message` を読むので、同じショートカットが使えます。フレームワークベースの
エージェント (`langgraph` / `microsoft-agent-framework`) には `echo` /
`generate_image_tool` に加えてサンドボックス化されたファイル操作ツール
（デフォルト: `read_file` / `list_directory` / `file_search`）と、任意有効化の
許可リスト方式 shell 実行ツール（`shell_exec`）も載せられます。LLM がユーザーの
リクエストに応じて適切なツールを選択します。`foundry-agent-service` は
 Azure AI Foundry Prompt Agent の薄いクライアントで、クライアント側ツールは
読み込まれません（ツール / knowledge は Foundry 側エージェント定義で設定）。

```bash
uv run agents-cli invoke --agent-type langgraph --message "Hello LangGraph"
uv run agents-cli invoke --agent-type github-copilot-sdk --message "Hello Copilot"
uv run agents-cli invoke --agent-type microsoft-agent-framework --message "Hello MAF"
uv run agents-cli invoke --agent-type foundry-agent-service --message "フランスの面積を平方マイルで教えて"
uv run agents-cli invoke --agent-type langgraph --message "Create an image of a red fox in watercolor style"
uv run agents-cli invoke --agent-type microsoft-agent-framework --message "Create an image of a red fox in watercolor style"
# ファイル操作（AGENTS_FILE_ROOT_DIR 配下のみ）
uv run agents-cli invoke --agent-type langgraph --message "ワークスペース直下のファイルを一覧表示して"
uv run agents-cli invoke --agent-type microsoft-agent-framework --message "ワークスペースの README.md を読んで"
# shell ツール（AGENTS_SHELL_TOOLS_ENABLED / AGENTS_SHELL_ALLOWED_COMMANDS が必要）
uv run agents-cli invoke --agent-type langgraph --message "shell_exec で terraform plan を実行して"
```

`langgraph` の echo 成功時レスポンス例:

```json
{
  "status": "succeeded",
  "result": {
    "message": "Hello LangGraph",
    "reply": "Hello LangGraph",
    "tool_calls": [
      {"name": "echo", "args": {"text": "Hello LangGraph"}}
    ]
  },
  "error": null
}
```

オプション:

| フラグ | 必須 | 説明 |
|--------|------|------|
| `--agent-type` | 必須 | 登録済みエージェント識別子 |
| `--payload` | 省略可 | JSON オブジェクト文字列（デフォルト `{}`） |
| `--context` | 省略可 | `AgentRequest.context` に渡す JSON オブジェクト文字列（デフォルト `{}`） |
| `--message` | 省略可 | `{"message": <value>}` を `--payload` にマージするショートカット |

### エージェントのメタ情報表示

```bash
uv run agents-cli info --agent-type langgraph
uv run agents-cli info --agent-type github-copilot-sdk
uv run agents-cli info --agent-type microsoft-agent-framework
uv run agents-cli info --agent-type foundry-agent-service
```

出力例:

```json
{
  "agent_type": "langgraph",
  "class": "LangGraphAgent",
  "module": "concierge.agents.infrastructure.langgraph_agent",
  "settings": {
    "langgraph_model": "azure_ai:gpt-5",
    "langgraph_system_prompt": "You are a helpful assistant. ..."
  }
}
```

このコマンドは LLM クライアントを生成しないので、Azure 認証情報が
未設定でも安全に実行できます。

## 設定

agents CLI が読むのは `AGENTS_*` 変数のみです。リポジトリ／キュー
バックエンドは `cloud_agent` や `chat` の関心事で、ここでは無関係です。

| 環境変数 | デフォルト | 説明 |
|---------|-----------|------|
| `AGENTS_LANGGRAPH_MODEL` | `azure_ai:gpt-5` | `langgraph` の `init_chat_model` で使うモデル文字列 |
| `AGENTS_LANGGRAPH_SYSTEM_PROMPT` | _(組み込み)_ | `langgraph` のシステムプロンプト。デフォルトでは `echo` と `generate_image_tool` を使い分けるよう LLM に指示します。 |
| `AGENTS_GITHUB_COPILOT_SDK_MODEL` | `gpt-5-mini` | `github-copilot-sdk` の `CopilotClient.create_session(model=...)` に渡すモデル名 |
| `AGENTS_GITHUB_COPILOT_SDK_SYSTEM_PROMPT` | _(組み込み)_ | `github-copilot-sdk` のシステムプロンプト（`create_session` に `system_message={"mode": "replace", "content": ...}` として渡される）。デフォルト: `You are a helpful coding assistant that provides code suggestions and explanations to users.` |
| `AGENTS_MICROSOFT_AGENT_FRAMEWORK_MODEL` | `gpt-5` | `microsoft-agent-framework` の `FoundryChatClient(model=...)` に渡すモデル文字列 |
| `AGENTS_MICROSOFT_AGENT_FRAMEWORK_SYSTEM_PROMPT` | _(組み込み)_ | `microsoft-agent-framework` のシステムプロンプト（`Agent(instructions=...)` に渡される）。デフォルトでは `echo` と `generate_image_tool` を使い分けるよう LLM に指示します。 |
| `AGENTS_FOUNDRY_AGENT_SERVICE_MODEL` | `gpt-5` | `foundry-agent-service` の `PromptAgentDefinition.model` に使う Foundry デプロイ名 |
| `AGENTS_FOUNDRY_AGENT_SERVICE_SYSTEM_PROMPT` | `You are a helpful assistant.` | `foundry-agent-service` の Foundry 側 `PromptAgentDefinition` に永続化される instructions |
| `AGENTS_FOUNDRY_AGENT_SERVICE_AGENT_NAME` | `concierge-foundry-agent` | `foundry-agent-service` で使う Foundry 側 Prompt Agent 名 |
| `AGENTS_FILE_ROOT_DIR` | `""`（`<cwd>/workspace`） | ファイル操作ツール（`read_file` / `list_directory` / `file_search` / 任意の書き込み系）の sandbox root |
| `AGENTS_FILE_TOOLS_ENABLED` | `read_file,list_directory,file_search` | 有効化するファイル操作ツールのカンマ区切り。`""` で全無効化 |
| `AGENTS_SHELL_TOOLS_ENABLED` | `""` | 有効化する shell ツール名のカンマ区切り。空なら無効（デフォルト・opt-in） |
| `AGENTS_SHELL_ALLOWED_COMMANDS` | `""` | `shell_exec` で許可するコマンド名のカンマ区切り（shell ツール有効時は必須） |
| `AGENTS_SHELL_ROOT_DIR` | `""`（`AGENTS_FILE_ROOT_DIR` にフォールバック） | shell 実行時の固定作業ディレクトリ |
| `AGENTS_SHELL_TIMEOUT_SECONDS` | `30` | コマンド実行タイムアウト（秒） |
| `AGENTS_SHELL_MAX_OUTPUT_BYTES` | `65536` | stdout/stderr 各ストリームの最大出力バイト数（超過時に truncate） |
| `AGENTS_IMAGE_MODEL` | `gpt-image-2` | Foundry 画像モデルのデプロイ名 |
| `AGENTS_IMAGE_SIZE` | `1024x1024` | 既定サイズ（`1024x1024` / `1536x1024` / `1024x1536` / `4K`） |
| `AGENTS_IMAGE_N` | `1` | 既定の生成枚数 |
| `AGENTS_IMAGE_API_VERSION` | `2025-04-01-preview` | `openai.AzureOpenAI` に渡す API バージョン |
| `CONCIERGE_TRACING_ENABLED` | `false` | `--tracing` を渡さずに tracing を有効化 |
| `CONCIERGE_MLFLOW_ENABLED` | `false` | `--mlflow` を渡さずに MLflow autologging を有効化 |

### 画像を直接生成する（LLM 経由なし）

`gpt-image-2` は現在 GA リージョンが限定的なため、`AZURE_AI_PROJECT_ENDPOINT`
が画像モデル未デプロイのリージョンを指す場合は、`gpt-image-2` をホストする
別の Foundry プロジェクトを `AZURE_AI_PROJECT_ENDPOINT_IMAGE` に設定してください。
`AZURE_AI_PROJECT_ENDPOINT_IMAGE` が空のときは共有の `AZURE_AI_PROJECT_ENDPOINT`
が使われます。

```bash
uv run agents-cli image generate \
  --prompt "A photo of a Shibuya crossing at night" \
  --size 1024x1024 \
  --n 1 \
  --output-dir ./out
```

オプション:

| フラグ | 必須 | 説明 |
|--------|------|------|
| `--prompt` | 必須 | 画像生成プロンプト |
| `--size` | 省略可 | 画像サイズ（既定: `AGENTS_IMAGE_SIZE`） |
| `--n` | 省略可 | 生成枚数（既定: `AGENTS_IMAGE_N`） |
| `--output-dir` | 省略可 | `.png` 出力先ディレクトリ（既定: `./generated_images`） |
| `--json` | 省略可 | JSON 全体を出力 |
| `--include-base64` | 省略可 | JSON 出力に `b64_json` を含める（未指定時は `null`） |

エージェント一覧や契約の詳細は
[Shared Agent Runtime 概要](index.ja.md) を参照してください。

shell ツールを有効化する `.env` 設定例:

```bash
AGENTS_SHELL_TOOLS_ENABLED=shell_exec
AGENTS_SHELL_ALLOWED_COMMANDS=terraform
# 任意:
# AGENTS_SHELL_ROOT_DIR=./workspace
# AGENTS_SHELL_TIMEOUT_SECONDS=30
# AGENTS_SHELL_MAX_OUTPUT_BYTES=65536
```

## tracing / MLflow を有効にして実行する例

```bash
export AZURE_AI_PROJECT_ENDPOINT="https://<your-foundry-endpoint>"
az login
uv run agents-cli \
  --tracing --mlflow --verbose \
  invoke --agent-type langgraph --message "trace me"
```

`github-copilot-sdk` の成功時レスポンス例（SDK セッションから
返ってきたアシスタント応答が `reply` にそのまま入ります）:

```json
{
  "status": "succeeded",
  "result": {
    "message": "Hello Copilot",
    "reply": "Hello Copilot",
    "model": "gpt-5-mini"
  },
  "error": null
}
```

> `github-copilot-sdk` はリクエストごとに `CopilotClient` を生成し、
> `create_session(model=..., system_message=...,
> on_permission_request=PermissionHandler.approve_all)` でセッションを
> 払い出し、ユーザーメッセージを `session.send` で送信、
> `SessionIdleData` を受信してから応答を返します。
> 受信した `AssistantMessageData.content` を連結したものが
> `result.reply` になります。実行には
> [GitHub Copilot CLI](https://github.com/github/copilot-cli) のインストール
> と認証が必要です。
