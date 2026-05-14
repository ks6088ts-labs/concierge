import logging
import os
import sys
import uuid
from collections.abc import Callable
from functools import lru_cache
from typing import Annotated, Any, Literal

import httpx
import typer
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, tool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver

from concierge.loggers import get_logger
from concierge.settings import (
    get_microsoft_foundry_settings,
    get_observability_settings,
)

DEFAULT_ENDPOINT = "http://localhost:8080"
DEFAULT_MODEL_STRING = "azure_ai:gpt-5"
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_SYSTEM_PROMPT = (
    "あなたは Todo アプリのアシスタントです。ユーザーのタスク管理を支援してください。"
    "必要に応じてツールを使ってタスクを作成・一覧・取得・更新・完了・削除します。"
    "典型的には『作成→一覧→完了』の順で正確に操作し、結果を簡潔に日本語で説明してください。"
)

app = typer.Typer(add_completion=False, help="LangGraph Todo Agent CLI")
logger = get_logger(__name__)

_tracing_enabled: bool = False


@app.callback()
def _global_options(
    tracing: Annotated[
        bool,
        typer.Option(
            "--tracing",
            "-t",
            help=(
                "Enable Microsoft Foundry / Azure Monitor tracing for LangChain runs. "
                "See https://learn.microsoft.com/en-us/azure/foundry/how-to/develop/langchain-traces"
            ),
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose (DEBUG) logging",
        ),
    ] = False,
    mlflow: Annotated[
        bool,
        typer.Option(
            "--mlflow",
            "-m",
            help=(
                "Enable MLflow autologging for LangChain / LangGraph runs. "
                "See https://mlflow.org/docs/latest/genai/tracing/integrations/listing/langgraph/"
            ),
        ),
    ] = False,
):
    """LangGraph Todo CLI - global options applied to every subcommand."""
    global _tracing_enabled
    _tracing_enabled = tracing
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
        logger.setLevel(logging.DEBUG)
    if mlflow:
        _enable_mlflow()


@lru_cache(maxsize=1)
def _enable_mlflow() -> None:
    """Enable MLflow autologging for LangChain / LangGraph."""
    import mlflow

    observability_settings = get_observability_settings()
    tracking_uri = observability_settings.mlflow_tracking_uri
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(observability_settings.mlflow_experiment_name)
    mlflow.langchain.autolog()
    logger.info("MLflow autologging enabled (tracking_uri=%s)", tracking_uri)


@lru_cache(maxsize=1)
def _get_tracer():
    """Build and cache AzureAIOpenTelemetryTracer."""
    from langchain_azure_ai.callbacks.tracers import AzureAIOpenTelemetryTracer

    return AzureAIOpenTelemetryTracer(
        project_endpoint=get_microsoft_foundry_settings().azure_ai_project_endpoint,
        credential=DefaultAzureCredential(),
        name="langgraph-vanilla",
    )


def _trace_config(extra: dict[str, Any] | None = None) -> RunnableConfig:
    """Return RunnableConfig and attach tracer only when tracing is enabled."""
    config: dict[str, Any] = dict(extra or {})
    if _tracing_enabled:
        callbacks = list(config.get("callbacks", []))
        callbacks.append(_get_tracer())
        config["callbacks"] = callbacks
    return RunnableConfig(**config)


def _resolve_endpoint(endpoint: str | None) -> str:
    """Resolve endpoint with precedence: CLI > env var > default."""
    return endpoint or os.getenv("TODO_API_ENDPOINT") or DEFAULT_ENDPOINT


def _to_api_status(status: str | None) -> str | None:
    """Map lowercase status literals to API enum values."""
    if status is None:
        return None
    mapping = {
        "todo": "TODO",
        "in_progress": "IN_PROGRESS",
        "done": "DONE",
    }
    return mapping.get(status.lower(), status)


def _http_error_dict(message: str, status_code: int = 0) -> dict[str, Any]:
    """Create a uniform error payload returned by tools."""
    return {"error": message, "status_code": status_code}


def _safe_request(
    client: httpx.Client,
    method: str,
    path: str,
    *,
    json: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> Any:
    """Execute a Todo API request and return JSON or an error dict."""
    logger.debug("HTTP %s %s json=%s params=%s", method, path, json, params)
    try:
        response = client.request(method=method, url=path, json=json, params=params)
    except httpx.RequestError as exc:
        logger.info("Todo API request failed: %s %s", method, path)
        return _http_error_dict(f"{exc.__class__.__name__}: {exc}")

    if response.status_code >= 400:
        logger.info("Todo API request returned HTTP %s for %s %s", response.status_code, method, path)
        detail: str
        try:
            payload = response.json()
            detail = str(payload)
        except ValueError:
            detail = response.text
        return _http_error_dict(detail, response.status_code)

    if response.status_code == 204 or not response.content:
        return {}

    try:
        return response.json()
    except ValueError:
        return _http_error_dict("Response body is not valid JSON", response.status_code)


def _build_tools(
    endpoint: str,
    timeout: float,
    *,
    transport: httpx.BaseTransport | None = None,
) -> list[BaseTool]:
    """Build Todo API tools backed by a shared HTTP client."""
    client = httpx.Client(base_url=endpoint, timeout=timeout, transport=transport)

    @tool
    def create_task(title: str, description: str | None = None) -> dict[str, Any]:
        """Create a new todo task by title and optional description."""
        logger.info("[tool] create_task")
        payload = {"title": title, "description": description}
        result = _safe_request(client, "POST", "/tasks", json=payload)
        logger.info("[tool] create_task completed")
        return result

    @tool
    def list_tasks(
        status: Literal["todo", "in_progress", "done"] | None = None,
    ) -> list[dict[str, Any]] | dict[str, Any]:
        """List tasks. Optionally filter by status: todo, in_progress, or done."""
        logger.info("[tool] list_tasks")
        api_status = _to_api_status(status)
        params = {"status": api_status} if api_status else None
        result = _safe_request(client, "GET", "/tasks", params=params)
        logger.info("[tool] list_tasks completed")
        return result

    @tool
    def get_task(task_id: str) -> dict[str, Any]:
        """Get a single task by task_id (UUID string)."""
        logger.info("[tool] get_task")
        result = _safe_request(client, "GET", f"/tasks/{task_id}")
        logger.info("[tool] get_task completed")
        return result

    @tool
    def update_task(
        task_id: str,
        title: str | None = None,
        description: str | None = None,
        status: Literal["todo", "in_progress", "done"] | None = None,
    ) -> dict[str, Any]:
        """Update task fields (title, description, status) by task_id."""
        logger.info("[tool] update_task")
        payload: dict[str, Any] = {}
        if title is not None:
            payload["title"] = title
        if description is not None:
            payload["description"] = description
        api_status = _to_api_status(status)
        if api_status is not None:
            payload["status"] = api_status
        result = _safe_request(client, "PATCH", f"/tasks/{task_id}", json=payload)
        logger.info("[tool] update_task completed")
        return result

    @tool
    def complete_task(task_id: str) -> dict[str, Any]:
        """Mark a task as complete by task_id."""
        logger.info("[tool] complete_task")
        result = _safe_request(client, "POST", f"/tasks/{task_id}/complete")
        logger.info("[tool] complete_task completed")
        return result

    @tool
    def delete_task(task_id: str) -> dict[str, Any]:
        """Delete a task by task_id."""
        logger.info("[tool] delete_task")
        result = _safe_request(client, "DELETE", f"/tasks/{task_id}")
        logger.info("[tool] delete_task completed")
        if isinstance(result, dict) and "error" in result:
            return result
        return {"deleted": True, "id": task_id}

    return [create_task, list_tasks, get_task, update_task, complete_task, delete_task]


def _build_agent(
    model: str,
    endpoint: str,
    timeout: float,
    system_prompt: str,
    checkpointer: BaseCheckpointSaver | None,
):
    """Build a ReAct agent backed by LangGraph and Todo API tools."""
    tools = _build_tools(endpoint=endpoint, timeout=timeout)
    chat_model = init_chat_model(model)
    return create_agent(
        model=chat_model,
        tools=tools,
        system_prompt=system_prompt,
        checkpointer=checkpointer,
    )


def _extract_text(content: Any) -> str:
    """Extract printable text from message content shapes."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text" and block.get("text"):
                    chunks.append(str(block["text"]))
            elif isinstance(block, str):
                chunks.append(block)
        return "".join(chunks)
    return str(content) if content is not None else ""


def _print_tool_event(tool_call: dict[str, Any]) -> None:
    """Print one tool call event to stderr."""
    name = tool_call.get("name", "unknown_tool")
    args = tool_call.get("args", {})
    args_repr = ", ".join(f"{k}={v!r}" for k, v in args.items()) if isinstance(args, dict) else repr(args)
    print(f"[tool] {name}({args_repr})", file=sys.stderr)


def _print_tool_events_from_messages(messages: list[Any]) -> None:
    """Print tool calls discovered in a message list."""
    printed: set[str] = set()
    for message in messages:
        tool_calls = getattr(message, "tool_calls", None)
        if not tool_calls:
            continue
        for tool_call in tool_calls:
            tool_call_id = str(tool_call.get("id", ""))
            if tool_call_id and tool_call_id in printed:
                continue
            if tool_call_id:
                printed.add(tool_call_id)
            _print_tool_event(tool_call)


def _render_tools(tools: list[BaseTool]) -> str:
    """Render tool names and signatures."""
    lines = ["Available tools:"]
    for tool_obj in tools:
        args = getattr(tool_obj, "args", {})
        signature = ", ".join(f"{name}: {meta.get('type', 'any')}" for name, meta in args.items())
        lines.append(f"- {tool_obj.name}({signature})")
    return "\n".join(lines)


def _dispatch_slash_command(
    text: str,
    *,
    thread_id: str,
    tools: list[BaseTool],
    thread_id_factory: Callable[[], str],
) -> tuple[bool, str]:
    """Handle slash commands. Returns (continue_loop, current_thread_id)."""
    normalized = text.strip().lower()
    if normalized in {"/exit", "/quit"}:
        return False, thread_id
    if normalized == "/reset":
        new_thread_id = thread_id_factory()
        print(f"Thread reset: {thread_id} -> {new_thread_id}")
        return True, new_thread_id
    if normalized == "/thread":
        print(thread_id)
        return True, thread_id
    if normalized == "/tools":
        print(_render_tools(tools))
        return True, thread_id
    if normalized == "/help":
        print("Commands: /exit, /quit, /reset, /help, /tools, /thread")
        print(_render_tools(tools))
        return True, thread_id

    print("Unknown command. Use /help to list available commands.")
    return True, thread_id


def _thread_config(thread_id: str) -> RunnableConfig:
    """Build a thread-scoped config and include optional tracing callbacks."""
    return _trace_config({"configurable": {"thread_id": thread_id}})


def _run_once(agent: Any, query: str, thread_id: str) -> str:
    """Execute a single-turn agent call and return final assistant text."""
    result = agent.invoke({"messages": [("user", query)]}, config=_thread_config(thread_id))
    messages = result.get("messages", [])
    if isinstance(messages, list):
        _print_tool_events_from_messages(messages)
        for message in reversed(messages):
            if isinstance(message, AIMessage):
                return _extract_text(message.content)
    return ""


def _run_repl(agent: Any, tools: list[BaseTool], initial_thread_id: str) -> None:
    """Run an interactive REPL with streaming responses and slash commands."""
    current_thread_id = initial_thread_id
    seen_tool_calls: set[str] = set()

    while True:
        try:
            text = input(">>> ").strip()
        except KeyboardInterrupt:
            print("\nExiting...")
            return

        if not text:
            continue
        if text.startswith("/"):
            should_continue, current_thread_id = _dispatch_slash_command(
                text,
                thread_id=current_thread_id,
                tools=tools,
                thread_id_factory=lambda: str(uuid.uuid4()),
            )
            if not should_continue:
                return
            continue

        config = _thread_config(current_thread_id)
        emitted_text = False
        for mode, event in agent.stream(
            {"messages": [("user", text)]},
            config=config,
            stream_mode=["messages", "updates"],
        ):
            if mode == "messages":
                chunk, _metadata = event
                content = _extract_text(getattr(chunk, "content", ""))
                if content:
                    print(content, end="", flush=True)
                    emitted_text = True
            elif mode == "updates" and isinstance(event, dict):
                for node_data in event.values():
                    if not isinstance(node_data, dict):
                        continue
                    messages = node_data.get("messages")
                    if not isinstance(messages, list):
                        continue
                    for message in messages:
                        tool_calls = getattr(message, "tool_calls", None)
                        if not tool_calls:
                            continue
                        for tool_call in tool_calls:
                            tool_call_id = str(tool_call.get("id", ""))
                            if tool_call_id and tool_call_id in seen_tool_calls:
                                continue
                            if tool_call_id:
                                seen_tool_calls.add(tool_call_id)
                            _print_tool_event(tool_call)
        if emitted_text:
            print()


@lru_cache(maxsize=1)
def _build_checkpointer() -> MemorySaver:
    """Build and cache a MemorySaver checkpointer."""
    return MemorySaver()


@app.command(help="Run a one-shot LangGraph Todo agent query")
def run(
    query: Annotated[
        str,
        typer.Option(
            "--query",
            "-q",
            help="Single-turn query sent to the Todo agent",
        ),
    ],
    endpoint: Annotated[
        str | None,
        typer.Option(
            "--endpoint",
            "-e",
            help="Todo Web API base URL (default: TODO_API_ENDPOINT or http://localhost:8080)",
        ),
    ] = None,
    model: Annotated[
        str,
        typer.Option(
            "--model",
            "-M",
            help="Model string passed to init_chat_model (e.g., azure_ai:gpt-5)",
        ),
    ] = DEFAULT_MODEL_STRING,
    timeout: Annotated[
        float,
        typer.Option(
            "--timeout",
            help="HTTP timeout seconds for Todo API tool calls",
        ),
    ] = DEFAULT_TIMEOUT_SECONDS,
    thread_id: Annotated[
        str | None,
        typer.Option(
            "--thread-id",
            help="LangGraph thread_id for checkpointed state",
        ),
    ] = None,
):
    """Run one query and print the final assistant response."""
    resolved_thread_id = thread_id or str(uuid.uuid4())
    resolved_endpoint = _resolve_endpoint(endpoint)
    try:
        agent = _build_agent(
            model=model,
            endpoint=resolved_endpoint,
            timeout=timeout,
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            checkpointer=_build_checkpointer(),
        )
        output = _run_once(agent, query=query, thread_id=resolved_thread_id)
        print(output)
    except Exception as exc:  # pragma: no cover - safety net for CLI UX
        logger.exception("run command failed")
        print(f"Error: {exc}", file=sys.stderr)
        raise typer.Exit(code=1) from exc


@app.command(help="Start an interactive multi-turn LangGraph Todo agent REPL")
def chat(
    endpoint: Annotated[
        str | None,
        typer.Option(
            "--endpoint",
            "-e",
            help="Todo Web API base URL (default: TODO_API_ENDPOINT or http://localhost:8080)",
        ),
    ] = None,
    model: Annotated[
        str,
        typer.Option(
            "--model",
            "-M",
            help="Model string passed to init_chat_model (e.g., azure_ai:gpt-5)",
        ),
    ] = DEFAULT_MODEL_STRING,
    timeout: Annotated[
        float,
        typer.Option(
            "--timeout",
            help="HTTP timeout seconds for Todo API tool calls",
        ),
    ] = DEFAULT_TIMEOUT_SECONDS,
    thread_id: Annotated[
        str | None,
        typer.Option(
            "--thread-id",
            help="LangGraph thread_id for checkpointed state",
        ),
    ] = None,
    system: Annotated[
        str,
        typer.Option(
            "--system",
            help="Override the default system prompt",
        ),
    ] = DEFAULT_SYSTEM_PROMPT,
):
    """Start an interactive REPL and keep state within the thread_id."""
    resolved_thread_id = thread_id or str(uuid.uuid4())
    resolved_endpoint = _resolve_endpoint(endpoint)
    tools = _build_tools(endpoint=resolved_endpoint, timeout=timeout)
    agent = create_agent(
        model=init_chat_model(model),
        tools=tools,
        system_prompt=system,
        checkpointer=_build_checkpointer(),
    )
    _run_repl(agent=agent, tools=tools, initial_thread_id=resolved_thread_id)


if __name__ == "__main__":
    if not load_dotenv(override=True, verbose=True):
        logging.warning("No .env file found; using defaults")
    app()
