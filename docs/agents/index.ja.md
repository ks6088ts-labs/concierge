---
title: 共有エージェントランタイム (日本語)
description: cloud_agent と chat で共有されるトランスポート非依存エージェント契約
---

## 概要

`concierge/agents` は、トランスポート非依存のエージェント契約
（`AgentRequest` / `AgentResponse` / `Agent` Protocol / `AgentRegistry`）を定義する
**共有バウンデッドコンテキスト**です。`cloud_agent` ワーカと `chat` の AI 応答経路の
両方から同一のエージェント実装を呼び出すことができます。

```mermaid
flowchart LR
    chat[chat ChatbotResponder] --> Registry
    cloud_agent[cloud_agent ワーカー] --> Registry
    Registry[AgentRegistry] --> Echo[EchoAgent]
    Registry --> LGE[LangGraphEchoAgent]
    Registry --> GCE[GitHubCopilotEchoAgent]
    subgraph agents["concierge/agents (共有カーネル)"]
        Registry
        Echo
        LGE
        GCE
    end
```

## ディレクトリ構成

```
concierge/agents/
  domain/
    exceptions.py          # AgentNotFoundError, AgentExecutionError
  application/
    contracts.py           # AgentRequest, AgentResponse, AgentChunk, Agent, StreamingAgent
    registry.py            # AgentRegistry
  infrastructure/
    echo_agent.py          # EchoAgent
    langgraph_echo_agent.py # LangGraphEchoAgent
    github_copilot_echo_agent.py # GitHubCopilotEchoAgent
    registry_factory.py    # get_agent_registry() (lru_cache)
```

## 契約

### AgentRequest / AgentResponse

```python
from concierge.agents.application.contracts import AgentRequest, AgentResponse

request = AgentRequest(
    agent_type="echo",
    payload={"message": "こんにちは"},
    context={"conversation_id": "<uuid>"},
)

response: AgentResponse = await agent.handle(request)
# response.status: "succeeded" | "failed"
# response.result: dict | None
# response.error: str | None
```

### Agent Protocol

```python
from typing import ClassVar
from concierge.agents.application.contracts import Agent, AgentRequest, AgentResponse

class MyAgent:
    agent_type: ClassVar[str] = "my-agent"

    async def handle(self, request: AgentRequest) -> AgentResponse:
        ...
```

## 組み込みエージェント

| agent_type | クラス | 説明 |
|------------|--------|------|
| `echo` | `EchoAgent` | `payload.message` をそのまま返す。LLM 不要。 |
| `langgraph-echo` | `LangGraphEchoAgent` | `echo` ツールを持つ LangGraph エージェント。Azure AI チャットモデルを使用。 |
| `github-copilot-echo` | `GitHubCopilotEchoAgent` | GitHub Copilot SDK のクライアント/セッション初期化のみを実行し、`payload.message` をそのまま返す（`session.send` は呼ばない）。 |

## 設定

エージェント設定は **`AGENTS_`** プレフィックスの環境変数から読み込まれます。

| 変数 | デフォルト | 説明 |
|------|-----------|------|
| `AGENTS_LANGGRAPH_MODEL` | `azure_ai:gpt-5` | `init_chat_model` に渡すモデル文字列。 |
| `AGENTS_LANGGRAPH_SYSTEM_PROMPT` | _(組み込み)_ | LangGraph エージェントへのシステムプロンプト。 |
| `AGENTS_GITHUB_COPILOT_MODEL` | `gpt-5` | `CopilotClient.create_session(model=...)` に渡すモデル名。 |
| `AGENTS_GITHUB_COPILOT_SYSTEM_PROMPT` | _(組み込み)_ | `github-copilot-echo` 用システムプロンプト（将来拡張の互換項目）。 |

## cloud_agent ワーカーからの利用

```bash
uv run cloud-agent-cli task dispatch \
  --agent-type langgraph-echo \
  --payload '{"message": "Hello LangGraph"}'
```

## chat からの利用

`CHAT_RESPONDER_BACKEND=agent` を設定すると、チャット返信が共有エージェント経由になります。

```bash
export CHAT_RESPONDER_BACKEND=agent
export CHAT_BOT_AGENT_TYPE=echo   # LLM 不要のスモークテスト
uv run chat-web
```

`github-copilot-echo` を使う場合:

```bash
export CHAT_RESPONDER_BACKEND=agent
export CHAT_BOT_AGENT_TYPE=github-copilot-echo
uv run chat-web
```

`github-copilot-echo` は LangChain/LangGraph ベースではないため、MLflow の
LangChain autologging では内部 SDK スパンは自動収集されません。

## 依存方向

`concierge.agents` は `concierge.chat` / `concierge.cloud_agent` / `concierge.todo`
に依存しません。この制約は `pyproject.toml` の `agents-no-service-coupling`
import-linter 契約によって静的に強制されます。
