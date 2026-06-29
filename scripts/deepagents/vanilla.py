import logging
from functools import lru_cache
from typing import Annotated, Any, Literal

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
):
    """Build a deep agent with a mock search tool, run one query, print the report."""
    from deepagents import create_deep_agent

    agent = create_deep_agent(
        model=model,
        tools=[internet_search],
        system_prompt=RESEARCH_INSTRUCTIONS,
    )
    result = agent.invoke(
        {"messages": [{"role": "user", "content": query}]},
        config=_trace_config(),
    )
    print(result["messages"][-1].content)


if __name__ == "__main__":
    if not load_dotenv(override=True, verbose=True):
        logging.warning("No .env file found; using defaults")
    app()
