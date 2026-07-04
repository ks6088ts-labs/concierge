---
title: Agents CLI Reference
description: Standalone CLI to exercise the shared agent runtime
---

## Installation

The `agents-cli` entry point is installed automatically when you run
`uv sync`.

```bash
uv run agents-cli --help
```

`agents-cli` calls `Agent.handle(AgentRequest)` directly against the shared
registry, so you can smoke-test a registered agent without bringing up the
`cloud_agent` task queue or the `chat` conversation flow.

## Global observability options

- `--tracing` toggles shared tracing state (`concierge-agents` tracer name).
- `--mlflow` enables `mlflow.langchain.autolog()` bootstrap.
- `--verbose` enables DEBUG logging.

Environment defaults (`CONCIERGE_TRACING_ENABLED` /
`CONCIERGE_MLFLOW_ENABLED`) are applied first via `bootstrap_from_env`, then
the explicit flags override.

## Commands

### List registered agent types

```bash
uv run agents-cli list
```

Output:

```json
["echo", "langgraph", "github-copilot-sdk", "microsoft-agent-framework", "foundry-agent-service"]
```

### List configured knowledge retrieval tools

```bash
uv run agents-cli knowledge list
```

Purpose: dry-run validation for `AGENTS_KNOWLEDGE__*` settings in CI/CD.
The command prints a JSON array with `name`, `collection`, `description`,
`top_k`, and `max_chars`.

Output example:

```json
[{"name":"search_docs","collection":"knowledge_default","description":"Search docs.","top_k":4,"max_chars":1200}]
```

Exit code is `0` on success and `1` when settings validation fails.

### Invoke an agent

Invokes `Agent.handle()` and prints `AgentResponse` as JSON. Exit code is
`0` when `status == "succeeded"` and `1` otherwise.

```bash
# Explicit JSON payload
uv run agents-cli invoke \
  --agent-type echo \
  --payload '{"message": "hello world"}'

# Shortcut: --message merges {"message": value} into --payload
uv run agents-cli invoke --agent-type echo --message "hello world"

# Pass request context (e.g. correlation IDs)
uv run agents-cli invoke \
  --agent-type echo \
  --message "hello" \
  --context '{"task_id": "00000000-0000-0000-0000-000000000001"}'
```

All built-in agents (`echo`, `langgraph`, `github-copilot-sdk`, `microsoft-agent-framework`, and `foundry-agent-service`) read `payload.message`,
so the same shortcut works for all of them. The client-side tool-capable agents
(`langgraph` / `github-copilot-sdk` / `microsoft-agent-framework`) carry `echo`,
`generate_image_tool`, sandboxed file-management tools (`read_file`,
`list_directory`, `file_search` by default), the single-page web reader
(`fetch_webpage` by default), and optional allowlisted shell execution
(`shell_exec`) — the LLM picks the right one based on the user's request.
`foundry-agent-service` is a thin client over the Azure AI Foundry Prompt Agent
and carries no client-side tools (tools and knowledge are configured on the
Foundry agent itself):

```bash
uv run agents-cli invoke --agent-type langgraph --message "Hello LangGraph"
uv run agents-cli invoke --agent-type github-copilot-sdk --message "Hello Copilot"
uv run agents-cli invoke --agent-type microsoft-agent-framework --message "Hello MAF"
uv run agents-cli invoke --agent-type foundry-agent-service --message "What is the size of France in square miles?"
uv run agents-cli invoke --agent-type langgraph --message "Create an image of a red fox in watercolor style"
uv run agents-cli invoke --agent-type microsoft-agent-framework --message "Create an image of a red fox in watercolor style"
# file tools (reads from AGENTS_FILE_ROOT_DIR sandbox)
uv run agents-cli invoke --agent-type langgraph --message "List files in the workspace root"
uv run agents-cli invoke --agent-type microsoft-agent-framework --message "Read README.md from the workspace"
# web fetch tool (single static HTTP(S) page; no search/crawl/JavaScript)
uv run agents-cli invoke --agent-type langgraph --message "Summarize https://example.com"
# shell tool (requires AGENTS_SHELL_TOOLS_ENABLED and AGENTS_SHELL_ALLOWED_COMMANDS)
uv run agents-cli invoke --agent-type langgraph --message "Run terraform plan with shell_exec"
```

A successful `langgraph` echo response looks like:

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

Options:

| Flag | Required | Description |
|------|----------|-------------|
| `--agent-type` | Yes | Registered agent identifier |
| `--payload` | No | JSON object string (default `{}`) |
| `--context` | No | JSON object string passed as `AgentRequest.context` (default `{}`) |
| `--message` | No | Shortcut; merges `{"message": <value>}` into `--payload` |

### Show agent metadata

```bash
uv run agents-cli info --agent-type langgraph
uv run agents-cli info --agent-type github-copilot-sdk
uv run agents-cli info --agent-type microsoft-agent-framework
uv run agents-cli info --agent-type foundry-agent-service
```

Output:

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

The command does not instantiate any LLM client, so it is safe to run
without Azure credentials.

## Configuration

The agents CLI only reads `AGENTS_*` variables. Repository / queue backends
belong to the `cloud_agent` and `chat` services and are not relevant here.

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENTS_LANGGRAPH_MODEL` | `azure_ai:gpt-5` | Model string for `init_chat_model` used by `langgraph` |
| `AGENTS_LANGGRAPH_SYSTEM_PROMPT` | _(built-in)_ | System prompt for `langgraph`. Default tells the LLM to pick between built-in tools such as `echo`, `generate_image_tool`, file tools, shell tools, and `fetch_webpage` based on the user's request. |
| `AGENTS_GITHUB_COPILOT_SDK_MODEL` | `gpt-5-mini` | Model name passed to `CopilotClient.create_session(model=...)` for `github-copilot-sdk` |
| `AGENTS_GITHUB_COPILOT_SDK_SYSTEM_PROMPT` | _(built-in)_ | System prompt for `github-copilot-sdk` (sent to `create_session` via `system_message={"mode": "replace", "content": ...}`). Default tells the LLM to pick between built-in tools such as `echo`, `generate_image_tool`, file tools, shell tools, and `fetch_webpage` based on the user's request. |
| `AGENTS_MICROSOFT_AGENT_FRAMEWORK_MODEL` | `gpt-5` | Model string passed to `FoundryChatClient(model=...)` for `microsoft-agent-framework` |
| `AGENTS_MICROSOFT_AGENT_FRAMEWORK_SYSTEM_PROMPT` | _(built-in)_ | System prompt for `microsoft-agent-framework` (passed as `Agent(instructions=...)`). Default tells the LLM to pick between built-in tools such as `echo`, `generate_image_tool`, file tools, shell tools, and `fetch_webpage` based on the user's request. |
| `AGENTS_FOUNDRY_AGENT_SERVICE_MODEL` | `gpt-5` | Foundry deployment name used as `PromptAgentDefinition.model` for `foundry-agent-service` |
| `AGENTS_FOUNDRY_AGENT_SERVICE_SYSTEM_PROMPT` | `You are a helpful assistant.` | Instructions persisted on the Foundry-side `PromptAgentDefinition` for `foundry-agent-service` |
| `AGENTS_FOUNDRY_AGENT_SERVICE_AGENT_NAME` | `concierge-foundry-agent` | Name of the Foundry-side Prompt Agent for `foundry-agent-service` |
| `AGENTS_FILE_ROOT_DIR` | `""` (`<cwd>/workspace`) | Sandbox root for file-management tools (`read_file`, `list_directory`, `file_search`, optional write tools) |
| `AGENTS_FILE_TOOLS_ENABLED` | `read_file,list_directory,file_search` | Comma-separated enabled file tools. Set to `""` to disable all file tools |
| `AGENTS_SHELL_TOOLS_ENABLED` | `""` | Comma-separated enabled shell tools. Keep empty to disable shell tools (default, opt-in) |
| `AGENTS_SHELL_ALLOWED_COMMANDS` | `""` | Comma-separated allowlisted command names for `shell_exec` (required when shell tools are enabled) |
| `AGENTS_SHELL_ROOT_DIR` | `""` (`AGENTS_FILE_ROOT_DIR` fallback) | Fixed working directory for shell commands |
| `AGENTS_SHELL_TIMEOUT_SECONDS` | `30` | Command timeout in seconds |
| `AGENTS_SHELL_MAX_OUTPUT_BYTES` | `65536` | Per-stream stdout/stderr output cap before truncation marker |
| `AGENTS_WEB_TOOLS_ENABLED` | `fetch_webpage` | Comma-separated enabled web tools. Set to `""` to disable web fetching |
| `AGENTS_WEB_FETCH_TIMEOUT_SECONDS` | `10` | Timeout for a single web page request |
| `AGENTS_WEB_FETCH_MAX_BYTES` | `3000000` | Maximum response bytes read before truncation |
| `AGENTS_WEB_FETCH_MAX_CONTENT_CHARS` | `8000` | Default maximum extracted Markdown characters returned to the model |
| `AGENTS_WEB_FETCH_USER_AGENT` | `conciergebot/1.0 (+https://github.com/ks6088ts-labs/concierge)` | User-Agent sent by `fetch_webpage` |
| `AGENTS_WEB_FETCH_ALLOW_DOMAINS` | `""` | Optional comma-separated domain allowlist |
| `AGENTS_WEB_FETCH_DENY_DOMAINS` | `""` | Optional comma-separated domain denylist |
| `AGENTS_WEB_FETCH_MAX_REDIRECTS` | `5` | Maximum redirects followed; every redirect target is re-validated |
| `AGENTS_WEB_FETCH_ALLOW_PRIVATE_IPS` | `false` | Development/testing escape hatch. Keep `false` in normal use to block SSRF to private, loopback, link-local, and metadata addresses |
| `AGENTS_IMAGE_MODEL` | `gpt-image-2` | Foundry image model deployment name |
| `AGENTS_IMAGE_SIZE` | `1024x1024` | Default image size (`1024x1024` / `1536x1024` / `1024x1536` / `4K`) |
| `AGENTS_IMAGE_N` | `1` | Default number of images per generation |
| `AGENTS_IMAGE_API_VERSION` | `2025-04-01-preview` | API version passed to `openai.AzureOpenAI` |
| `CONCIERGE_TRACING_ENABLED` | `false` | Enable tracing without passing `--tracing` |
| `CONCIERGE_MLFLOW_ENABLED` | `false` | Enable MLflow autologging without passing `--mlflow` |

### Generate images directly (without LLM mediation)

`gpt-image-2` is currently only generally available in a limited set of
Foundry regions. If `AZURE_AI_PROJECT_ENDPOINT` points at a region where it
is not deployed, set `AZURE_AI_PROJECT_ENDPOINT_IMAGE` to a Foundry project
that hosts the `gpt-image-2` deployment. When `AZURE_AI_PROJECT_ENDPOINT_IMAGE`
is empty, the shared `AZURE_AI_PROJECT_ENDPOINT` is used.

```bash
uv run agents-cli image generate \
  --prompt "A photo of a Shibuya crossing at night" \
  --size 1024x1024 \
  --n 1 \
  --output-dir ./out
```

Options:

| Flag | Required | Description |
|------|----------|-------------|
| `--prompt` | Yes | Image prompt |
| `--size` | No | Image size (defaults to `AGENTS_IMAGE_SIZE`) |
| `--n` | No | Number of images (defaults to `AGENTS_IMAGE_N`) |
| `--output-dir` | No | Output directory for `.png` files (defaults to `./generated_images`) |
| `--json` | No | Print full JSON payload |
| `--include-base64` | No | Include `b64_json` in JSON output (otherwise masked as `null`) |

See the [Shared Agent Runtime overview](index.md) for the full agent
catalogue and contract reference.

Example `.env` snippet for shell tool opt-in:

```bash
AGENTS_SHELL_TOOLS_ENABLED=shell_exec
AGENTS_SHELL_ALLOWED_COMMANDS=terraform
# Optional overrides:
# AGENTS_SHELL_ROOT_DIR=./workspace
# AGENTS_SHELL_TIMEOUT_SECONDS=30
# AGENTS_SHELL_MAX_OUTPUT_BYTES=65536
```

Example `.env` snippet for restricting web fetches to selected public domains:

```bash
AGENTS_WEB_TOOLS_ENABLED=fetch_webpage
AGENTS_WEB_FETCH_ALLOW_DOMAINS=example.com,docs.python.org
# AGENTS_WEB_FETCH_DENY_DOMAINS=tracking.example
# AGENTS_WEB_FETCH_MAX_CONTENT_CHARS=8000
```

## Running with tracing and MLflow

```bash
export AZURE_AI_PROJECT_ENDPOINT="https://<your-foundry-endpoint>"
az login
uv run agents-cli \
  --tracing --mlflow --verbose \
  invoke --agent-type langgraph --message "trace me"
```

Successful `github-copilot-sdk` output (the assistant reply text
returned by the SDK session is surfaced under `reply`):

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

> The `github-copilot-sdk` agent opens a fresh `CopilotClient` per
> request, calls `create_session(model=..., system_message=...,
> on_permission_request=PermissionHandler.approve_all)`, sends the user
> message over the session and waits for `SessionIdleData` before
> returning. The accumulated `AssistantMessageData.content` becomes
> `result.reply`. Running this command therefore requires the
> [GitHub Copilot CLI](https://github.com/github/copilot-cli) to be
> installed and authenticated.
