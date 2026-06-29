import asyncio
import json
import logging
import uuid
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal, cast

import typer
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
from langchain_core.runnables import RunnableConfig

from concierge.loggers import enable_verbose_logging, get_logger
from concierge.settings import (
    get_microsoft_foundry_settings,
    get_observability_settings,
)

# ``create_deep_agent`` accepts a ``"<provider>:<model>"`` model string and
# forwards it to ``init_chat_model`` internally, matching the rest of the repo.
DEFAULT_MODEL_STRING = "azure_ai:gpt-5"
DEFAULT_QUERY = "What is langgraph?"

# Repository root resolved from this file: scripts/deepagents/vanilla.py -> repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]

# System prompt to steer the agent to be an expert researcher (from the quickstart).
RESEARCH_INSTRUCTIONS = """You are an expert researcher. Your job is to conduct thorough \
research and then write a polished report.

You have access to an internet search tool as your primary means of gathering information.

## `internet_search`

Use this to run an internet search for a given query. You can specify the max number of \
results to return, the topic, and whether raw content should be included.
"""

app = typer.Typer(add_completion=False, help="Deep Agents quickstart CLI")
logger = get_logger(__name__)

# Module-level state for the global ``--tracing`` flag, set by the Typer
# callback below and consumed by ``_trace_config``.
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
    """Deep Agents CLI - global options applied to every subcommand."""
    global _tracing_enabled
    _tracing_enabled = tracing
    if verbose:
        enable_verbose_logging()
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
    """Build and cache the ``AzureAIOpenTelemetryTracer`` instance."""
    from langchain_azure_ai.callbacks.tracers import AzureAIOpenTelemetryTracer

    return AzureAIOpenTelemetryTracer(
        project_endpoint=get_microsoft_foundry_settings().azure_ai_project_endpoint,
        credential=DefaultAzureCredential(),
        name="deepagents-vanilla",
    )


def _trace_config(extra: dict[str, Any] | None = None) -> RunnableConfig:
    """Return a runnable ``config`` dict, attaching the tracer when enabled."""
    config: dict[str, Any] = dict(extra or {})
    if _tracing_enabled:
        callbacks = list(config.get("callbacks", []))
        callbacks.append(_get_tracer())
        config["callbacks"] = callbacks
    return RunnableConfig(**config)


def _build_artifacts_backend():
    """Build a ``FilesystemBackend`` rooted at ``artifacts/<timestamp>``.

    Agent output is the only concern here: paths like ``/report.md`` resolve to
    ``artifacts/<timestamp>/report.md`` and survive across runs.
    """
    from deepagents.backends import FilesystemBackend

    timestamp = datetime.now().strftime("%Y%m%d%H%M")
    artifacts_dir = REPO_ROOT / "artifacts" / timestamp
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Saving agent artifacts to %s", artifacts_dir)
    return FilesystemBackend(root_dir=artifacts_dir, virtual_mode=True)


def _build_backend(skill_sources: list[str] | None):
    """Output goes to ``artifacts/<timestamp>``; skills mount read-only at ``/skills/``.

    The two concerns stay independent: output always lands in the artifacts dir,
    and skills (if any) are routed to a repo-rooted backend so their SKILL.md
    files resolve without affecting where the agent writes.
    """
    artifacts = _build_artifacts_backend()
    if not skill_sources:
        return artifacts
    from deepagents.backends import CompositeBackend, FilesystemBackend

    repo = FilesystemBackend(root_dir=REPO_ROOT, virtual_mode=True)
    return CompositeBackend(default=artifacts, routes={"/skills/": repo})


def _resolve_skill_sources(skill_dirs: list[Path]) -> list[str]:
    """Map skill directories to ``/skills/<repo-relative>`` mount paths.

    Each directory is validated to exist and to live under the repo root so it is
    reachable through the ``/skills/`` route of the composite backend.
    """
    sources: list[str] = []
    for raw in skill_dirs:
        skill_path = raw.expanduser().resolve()
        if not skill_path.is_dir():
            raise typer.BadParameter(f"Skills directory not found: {skill_path}")
        try:
            relative = skill_path.relative_to(REPO_ROOT)
        except ValueError as exc:
            msg = f"Skills directory must be under the repo root ({REPO_ROOT}): {skill_path}"
            raise typer.BadParameter(msg) from exc
        sources.append(f"/skills/{relative.as_posix()}")
        logger.info("Loading skills from %s", skill_path)
    return sources


def _normalize_mcp_servers(raw: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Normalize an mcp.json document into MultiServerMCPClient connections.

    Accepts both VS Code style ``{"servers": {...}}`` and a flat
    ``{name: {...}}`` mapping. Each server's transport is inferred from an
    explicit ``transport``/``type`` field, else a ``url`` implies streamable_http
    and a ``command`` implies stdio.
    """
    servers = raw.get("servers", raw) if isinstance(raw, dict) else {}
    type_map = {"http": "streamable_http", "streamable_http": "streamable_http", "sse": "sse", "stdio": "stdio"}
    connections: dict[str, dict[str, Any]] = {}
    for name, cfg in servers.items():
        if not isinstance(cfg, dict):
            continue
        conn = {k: v for k, v in cfg.items() if k != "type"}
        transport = conn.get("transport") or type_map.get(str(cfg.get("type", "")).lower())
        if transport is None:
            transport = "stdio" if "command" in conn else "streamable_http"
        conn["transport"] = transport
        connections[name] = conn
    return connections


def _build_mcp_tools(mcp_config: Path) -> list[Any]:
    """Load MCP tools from a config file via MultiServerMCPClient."""
    from langchain_mcp_adapters.client import MultiServerMCPClient

    if not mcp_config.is_file():
        raise typer.BadParameter(f"MCP config file not found: {mcp_config}")
    connections = _normalize_mcp_servers(json.loads(mcp_config.read_text(encoding="utf-8")))
    if not connections:
        logger.warning("No MCP servers found in %s", mcp_config)
        return []
    logger.info("Connecting to MCP servers: %s", ", ".join(connections))
    tools = asyncio.run(MultiServerMCPClient(cast("Any", connections)).get_tools())
    logger.info("Loaded %d MCP tool(s)", len(tools))
    return tools


def _resolve_system_prompt(system: str) -> str:
    """Return the system prompt, reading from a file when prefixed with ``@``."""
    if system.startswith("@"):
        prompt_path = Path(system[1:]).expanduser()
        if not prompt_path.is_file():
            raise typer.BadParameter(f"System prompt file not found: {prompt_path}")
        return prompt_path.read_text(encoding="utf-8")
    return system


def _run_loop(agent: Any, thread_id: str) -> None:
    """Interactive multi-turn REPL; state persists via thread_id + checkpointer."""
    config = _trace_config({"configurable": {"thread_id": thread_id}})
    print("Interactive deep agent. Type /exit to quit.")
    while True:
        try:
            text = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            return
        if not text:
            continue
        if text.lower() in {"/exit", "/quit"}:
            return
        result = asyncio.run(agent.ainvoke({"messages": [{"role": "user", "content": text}]}, config=config))
        print(result["messages"][-1].content)


def internet_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
    include_raw_content: bool = False,
):
    """Run a web search.

    Mock implementation: returns deterministic fake results so the sample stays
    dependency-free (no Tavily/SerpAPI key required). Swap the body for a real
    search client (e.g. TavilyClient) for production use.
    """
    logger.info("[tool] internet_search query=%r topic=%s max_results=%d", query, topic, max_results)
    return {
        "query": query,
        "topic": topic,
        "results": [
            {
                "title": f"Mock result {i + 1} for {query!r}",
                "url": f"https://example.com/{topic}/{i + 1}",
                "content": f"Placeholder summary {i + 1} about {query!r}.",
                "raw_content": f"Raw content {i + 1}" if include_raw_content else None,
            }
            for i in range(max_results)
        ],
    }


@app.command(help="Run an expert research deep agent (faithful to the quickstart)")
def run(
    query: Annotated[
        str,
        typer.Option(
            "--query",
            "-q",
            help="Single-turn query sent to the deep agent",
        ),
    ] = DEFAULT_QUERY,
    model: Annotated[
        str,
        typer.Option(
            "--model",
            "-M",
            help="Model string for create_deep_agent (e.g., azure_ai:gpt-5 or openai:gpt-5)",
        ),
    ] = DEFAULT_MODEL_STRING,
    loop: Annotated[
        bool,
        typer.Option(
            "--loop",
            "-l",
            help="Start an interactive multi-turn REPL instead of a single query",
        ),
    ] = False,
    mcp_config: Annotated[
        Path | None,
        typer.Option(
            "--mcp-config",
            help="Path to an mcp.json file (VS Code style or flat) to load MCP tools",
        ),
    ] = None,
    skills: Annotated[
        list[Path] | None,
        typer.Option(
            "--skills",
            "-s",
            help="Skills directory to load (repeatable); must live under the repo root",
        ),
    ] = None,
    system: Annotated[
        str,
        typer.Option(
            "--system",
            help="System prompt; prefix with @ to read from a file (e.g., @prompt.md)",
        ),
    ] = RESEARCH_INSTRUCTIONS,
):
    """Build a deep agent with a mock search tool; run one query or an interactive loop."""
    from deepagents import create_deep_agent
    from langgraph.checkpoint.memory import MemorySaver

    system_prompt = _resolve_system_prompt(system)
    tools: list[Any] = [internet_search]
    if mcp_config is not None:
        tools.extend(_build_mcp_tools(mcp_config))

    skill_sources = _resolve_skill_sources(skills) if skills else None
    backend = _build_backend(skill_sources)

    agent = create_deep_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        backend=backend,
        skills=skill_sources,
        checkpointer=MemorySaver() if loop else None,
    )

    if loop:
        _run_loop(agent, thread_id=str(uuid.uuid4()))
        return

    result = asyncio.run(
        agent.ainvoke(
            {"messages": [{"role": "user", "content": query}]},
            config=_trace_config(),
        )
    )
    print(result["messages"][-1].content)


if __name__ == "__main__":
    if not load_dotenv(override=True, verbose=True):
        logging.warning("No .env file found; using defaults")
    app()
