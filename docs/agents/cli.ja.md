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
["echo", "langgraph-echo", "github-copilot-echo", "microsoft-agent-framework-echo"]
```

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

組み込みエージェント（`echo` / `langgraph-echo` / `github-copilot-echo` / `microsoft-agent-framework-echo`）は
`payload.message` を読むので、同じショートカットが使えます。

```bash
uv run agents-cli invoke --agent-type langgraph-echo --message "Hello LangGraph"
uv run agents-cli invoke --agent-type github-copilot-echo --message "Hello Copilot"
uv run agents-cli invoke --agent-type microsoft-agent-framework-echo --message "Hello MAF"
```

`langgraph-echo` の成功時レスポンス例:

```json
{
  "status": "succeeded",
  "result": {
    "echo": "Hello LangGraph",
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
uv run agents-cli info --agent-type langgraph-echo
uv run agents-cli info --agent-type github-copilot-echo
uv run agents-cli info --agent-type microsoft-agent-framework-echo
```

出力例:

```json
{
  "agent_type": "langgraph-echo",
  "class": "LangGraphEchoAgent",
  "module": "concierge.agents.infrastructure.langgraph_echo_agent",
  "settings": {
    "langgraph_model": "azure_ai:gpt-5",
    "langgraph_system_prompt": "You are a minimal echo agent. ..."
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
| `AGENTS_LANGGRAPH_MODEL` | `azure_ai:gpt-5` | `langgraph-echo` の `init_chat_model` で使うモデル文字列 |
| `AGENTS_LANGGRAPH_SYSTEM_PROMPT` | _(組み込み)_ | `langgraph-echo` のシステムプロンプト |
| `AGENTS_GITHUB_COPILOT_MODEL` | `gpt-5-mini` | `github-copilot-echo` の `CopilotClient.create_session(model=...)` に渡すモデル名 |
| `AGENTS_GITHUB_COPILOT_SYSTEM_PROMPT` | _(組み込み)_ | `github-copilot-echo` のシステムプロンプト（`create_session` に `system_message={"mode": "replace", "content": ...}` として渡される）。デフォルト: `You are a helpful coding assistant that provides code suggestions and explanations to users.` |
| `AGENTS_MICROSOFT_AGENT_FRAMEWORK_MODEL` | `gpt-5` | `microsoft-agent-framework-echo` の `FoundryChatClient(model=...)` に渡すモデル文字列 |
| `AGENTS_MICROSOFT_AGENT_FRAMEWORK_SYSTEM_PROMPT` | _(組み込み)_ | `microsoft-agent-framework-echo` のシステムプロンプト（`Agent(instructions=...)` に渡される） |
| `CONCIERGE_TRACING_ENABLED` | `false` | `--tracing` を渡さずに tracing を有効化 |
| `CONCIERGE_MLFLOW_ENABLED` | `false` | `--mlflow` を渡さずに MLflow autologging を有効化 |

エージェント一覧や契約の詳細は
[Shared Agent Runtime 概要](index.ja.md) を参照してください。

## tracing / MLflow を有効にして実行する例

```bash
export AZURE_AI_PROJECT_ENDPOINT="https://<your-foundry-endpoint>"
az login
uv run agents-cli \
  --tracing --mlflow --verbose \
  invoke --agent-type langgraph-echo --message "trace me"
```

`github-copilot-echo` の成功時レスポンス例（SDK セッションから
返ってきたアシスタント応答が `reply` にそのまま入ります）:

```json
{
  "status": "succeeded",
  "result": {
    "echo": "Hello Copilot",
    "reply": "Hello Copilot",
    "model": "gpt-5-mini"
  },
  "error": null
}
```

> `github-copilot-echo` はリクエストごとに `CopilotClient` を生成し、
> `create_session(model=..., system_message=...,
> on_permission_request=PermissionHandler.approve_all)` でセッションを
> 払い出し、ユーザーメッセージを `session.send` で送信、
> `SessionIdleData` を受信してから応答を返します。
> 受信した `AssistantMessageData.content` を連結したものが
> `result.reply` になります。実行には
> [GitHub Copilot CLI](https://github.com/github/copilot-cli) のインストール
> と認証が必要です。
