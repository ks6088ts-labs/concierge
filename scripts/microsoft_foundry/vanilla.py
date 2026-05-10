import asyncio
import logging
import os
from functools import lru_cache
from typing import Annotated, Any

import typer
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_azure_ai.chat_models import AzureAIOpenAIApiChatModel
from langchain_core.runnables import RunnableConfig

from concierge.loggers import get_logger

DEFAULT_SETTINGS = {
    "query": "Hello, how are you doing today?",
    "model_provider": "azure_ai",
    "model": "gpt-5",
    "embedding_model": "text-embedding-3-small",
    "embedding_text": "The quick brown fox jumps over the lazy dog.",
}

# ``init_chat_model`` / ``init_embeddings`` accept a ``"<provider>:<model>"`` string,
# so derive them from ``DEFAULT_SETTINGS`` instead of duplicating the values.
DEFAULT_MODEL_STRING = f"{DEFAULT_SETTINGS['model_provider']}:{DEFAULT_SETTINGS['model']}"
DEFAULT_EMBEDDING_MODEL_STRING = f"{DEFAULT_SETTINGS['model_provider']}:{DEFAULT_SETTINGS['embedding_model']}"

app = typer.Typer(
    add_completion=False,
    help="Microsoft Foundry CLI",
)

logger = get_logger(__name__)

# Module-level state for the global ``--tracing`` / ``--mlflow`` flags,
# set by the Typer callback below and consumed by ``_trace_config``.
_tracing_enabled: bool = False
_mlflow_enabled: bool = False


@app.callback()
def _global_options(
    tracing: Annotated[
        bool,
        typer.Option(
            "--tracing",
            "-t",
            help=(
                "Enable Azure AI Foundry / Azure Monitor tracing for LangChain runs. "
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
    """Microsoft Foundry CLI - global options applied to every subcommand."""
    global _tracing_enabled, _mlflow_enabled
    _tracing_enabled = tracing
    _mlflow_enabled = mlflow
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
        logger.setLevel(logging.DEBUG)
    if mlflow:
        _enable_mlflow()


@lru_cache(maxsize=1)
def _enable_mlflow() -> None:
    """Enable MLflow autologging for LangChain / LangGraph.

    Follows the integration guide at
    https://mlflow.org/docs/latest/genai/tracing/integrations/listing/langgraph/
    Tracking URI and experiment name can be customised via the standard
    ``MLFLOW_TRACKING_URI`` and ``MLFLOW_EXPERIMENT_NAME`` env vars.
    """
    import mlflow

    # Default to the local server started by ``make mlflow`` so traces are
    # visible in the UI out of the box. Override with ``MLFLOW_TRACKING_URI``.
    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI", "http://127.0.0.1:5000")
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(os.environ.get("MLFLOW_EXPERIMENT_NAME", "microsoft-foundry-vanilla"))
    mlflow.langchain.autolog()
    logger.info("MLflow autologging enabled (tracking_uri=%s)", tracking_uri)


@lru_cache(maxsize=1)
def _get_tracer():
    """Build (and cache) the ``AzureAIOpenTelemetryTracer`` instance.

    Imported lazily so commands that don't need tracing don't pay the import
    cost. The docs recommend creating a single tracer instance and reusing it
    across the workflow.
    """
    from langchain_azure_ai.callbacks.tracers import AzureAIOpenTelemetryTracer

    return AzureAIOpenTelemetryTracer(
        project_endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"],
        credential=DefaultAzureCredential(),
        name="microsoft-foundry-vanilla",
    )


def _trace_config(extra: dict[str, Any] | None = None) -> RunnableConfig:
    """Return a runnable ``config`` dict, attaching the tracer when enabled.

    Use this helper for every ``invoke`` / ``ainvoke`` / ``stream`` call so
    that toggling ``--tracing on/off`` flows through uniformly.
    """
    config: dict[str, Any] = dict(extra or {})
    if _tracing_enabled:
        callbacks = list(config.get("callbacks", []))
        callbacks.append(_get_tracer())
        config["callbacks"] = callbacks
    return RunnableConfig(**config)


@app.command(
    help="Use chat models: https://learn.microsoft.com/en-us/azure/foundry/how-to/develop/langchain-models#use-chat-models"
)
def hello_world(
    query: Annotated[
        str,
        typer.Option(
            "--query",
            "-q",
            help="Query to ask the model",
        ),
    ] = DEFAULT_SETTINGS["query"],
    model_string: Annotated[
        str,
        typer.Option(
            "--model",
            "-m",
            help="Model to use (e.g., 'azure_ai:gpt-5')",
        ),
    ] = DEFAULT_MODEL_STRING,
):
    chat_model = init_chat_model(model_string)
    response = chat_model.invoke(query, config=_trace_config())
    response.pretty_print()


@app.command(
    help="Configurable models: https://learn.microsoft.com/en-us/azure/foundry/how-to/develop/langchain-models#configurable-models",
)
def configurable(
    query: Annotated[
        str,
        typer.Option(
            "--query",
            "-q",
            help="Query to ask the model",
        ),
    ] = DEFAULT_SETTINGS["query"],
    model_provider: Annotated[
        str,
        typer.Option(
            "--model-provider",
            "-mp",
            help="Model provider to use (e.g., 'azure_ai')",
        ),
    ] = DEFAULT_SETTINGS["model_provider"],
    model: Annotated[
        str,
        typer.Option(
            "--model",
            "-m",
            help="Model to use (e.g., 'gpt-5')",
        ),
    ] = DEFAULT_SETTINGS["model"],
    temperature: Annotated[
        float,
        typer.Option(
            "--temperature",
            "-t",
            help="Temperature for response generation (0-1)",
        ),
    ] = 0,
):
    configurable_model = init_chat_model(
        model_provider=model_provider,
        temperature=temperature,
        credential=DefaultAzureCredential(),
    )
    response = configurable_model.invoke(
        input=query,
        config=_trace_config({"configurable": {"model": model}}),
    )
    response.pretty_print()


@app.command(
    help="Configure clients directly: https://learn.microsoft.com/en-us/azure/foundry/how-to/develop/langchain-models#configure-clients-directly"
)
def direct_client(
    query: Annotated[
        str,
        typer.Option(
            "--query",
            "-q",
            help="Query to ask the model",
        ),
    ] = DEFAULT_SETTINGS["query"],
    model: Annotated[
        str,
        typer.Option(
            "--model",
            "-m",
            help="Model to use (e.g., 'gpt-5')",
        ),
    ] = DEFAULT_SETTINGS["model"],
):
    chat_model = AzureAIOpenAIApiChatModel(
        project_endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"],
        credential=DefaultAzureCredential(),
        model=model,
    )
    chat_model.invoke(query, config=_trace_config()).pretty_print()


@app.command(
    help="Run asynchronous calls: https://learn.microsoft.com/en-us/azure/foundry/how-to/develop/langchain-models#run-asynchronous-calls"
)
def async_call(
    query: Annotated[
        str,
        typer.Option(
            "--query",
            "-q",
            help="Query to ask the model",
        ),
    ] = DEFAULT_SETTINGS["query"],
    model: Annotated[
        str,
        typer.Option(
            "--model",
            "-m",
            help="Model to use (e.g., 'gpt-5')",
        ),
    ] = DEFAULT_SETTINGS["model"],
):
    async def main():
        from azure.identity.aio import DefaultAzureCredential as DefaultAzureCredentialAsync

        credential = DefaultAzureCredentialAsync()
        try:
            chat_model = AzureAIOpenAIApiChatModel(
                project_endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"],
                credential=credential,
                model=model,
            )
            response = await chat_model.ainvoke(query, config=_trace_config())
            response.pretty_print()
        finally:
            await credential.close()

    asyncio.run(main())


@app.command(
    help="Reasoning: https://learn.microsoft.com/en-us/azure/foundry/how-to/develop/langchain-models#reasoning"
)
def reasoning(
    query: Annotated[
        str,
        typer.Option(
            "--query",
            "-q",
            help="Query to ask the model",
        ),
    ] = "Why do parrots have colorful feathers?",
    model_string: Annotated[
        str,
        typer.Option(
            "--model",
            "-m",
            help="Model to use (e.g., 'azure_ai:DeepSeek-R1-0528')",
        ),
    ] = DEFAULT_MODEL_STRING,
):
    chat_model = init_chat_model(model_string)

    for chunk in chat_model.stream(query, config=_trace_config()):
        reasoning_steps = [r for r in chunk.content_blocks if r["type"] == "reasoning"]
        print(reasoning_steps if reasoning_steps else chunk.text, end="")

    print("\n")


@app.command(
    help="Server-side tools: https://learn.microsoft.com/en-us/azure/foundry/how-to/develop/langchain-models#server-side-tools"
)
def server_side_tools(
    query: Annotated[
        str,
        typer.Option(
            "--query",
            "-q",
            help="Query to ask the model",
        ),
    ] = "What is the current price of gold? Give me the answer in one sentence.",
    model_string: Annotated[
        str,
        typer.Option(
            "--model",
            "-m",
            help="Model to use (e.g., 'azure_ai:gpt-5')",
        ),
    ] = DEFAULT_MODEL_STRING,
):
    from langchain_azure_ai.tools.builtin import WebSearchTool

    model = init_chat_model(
        model_string,
        credential=DefaultAzureCredential(),
    )
    model_with_web_search = model.bind_tools(
        [
            WebSearchTool(),
        ]
    )

    result = model_with_web_search.invoke(query, config=_trace_config())
    last_block = result.content[-1] if isinstance(result.content, list) else result.content
    if isinstance(last_block, dict):
        print(last_block.get("text", ""))
    else:
        print(last_block)


@app.command(
    help="Use Foundry models in agents: https://learn.microsoft.com/en-us/azure/foundry/how-to/develop/langchain-models#use-foundry-models-in-agents"
)
def use_in_agents(
    query: Annotated[
        str,
        typer.Option(
            "--query",
            "-q",
            help="Query to ask the model",
        ),
    ] = DEFAULT_SETTINGS["query"],
    model_string: Annotated[
        str,
        typer.Option(
            "--model",
            "-m",
            help="Model to use (e.g., 'azure_ai:gpt-5')",
        ),
    ] = DEFAULT_MODEL_STRING,
    system_prompt: Annotated[
        str,
        typer.Option(
            "--system-prompt",
            "-s",
            help="System prompt for the agent",
        ),
    ] = "You're an informational agent. Answer questions cheerfully.",
):
    from langchain.agents import create_agent

    agent = create_agent(
        model=model_string,
        system_prompt=system_prompt,
    )

    response = agent.invoke({"messages": query}, config=_trace_config())
    response["messages"][-1].pretty_print()


def _resource_openai_v1_endpoint() -> str:
    """Return the resource-level OpenAI-compatible endpoint.

    Azure AI Foundry's project-scoped path
    (``/api/projects/<project>/openai/v1/embeddings``) currently does not
    serve the embeddings API. Embeddings are only available on the
    resource-level path (``/openai/v1/embeddings``), so we strip the
    ``/api/projects/...`` segment from ``AZURE_AI_PROJECT_ENDPOINT``.
    """
    project_endpoint = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
    resource = project_endpoint.split("/api/projects/", 1)[0]
    return f"{resource}/openai/v1"


@app.command(
    help="Use embedding models: https://learn.microsoft.com/en-us/azure/foundry/how-to/develop/langchain-models#use-embedding-models"
)
def embeddings(
    text: Annotated[
        str,
        typer.Option(
            "--text",
            "-t",
            help="Text to embed",
        ),
    ] = DEFAULT_SETTINGS["embedding_text"],
    model_string: Annotated[
        str,
        typer.Option(
            "--model",
            "-m",
            help="Embedding model to use (e.g., 'azure_ai:text-embedding-3-small')",
        ),
    ] = DEFAULT_EMBEDDING_MODEL_STRING,
):
    from langchain.embeddings import init_embeddings

    # Override the project endpoint with the resource-level OpenAI v1 endpoint
    # because the project-scoped path does not currently serve embeddings.
    embed_model = init_embeddings(
        model_string,
        endpoint=_resource_openai_v1_endpoint(),
        credential=DefaultAzureCredential(),
        api_version="preview",
    )
    vector = embed_model.embed_query(text)
    print(f"Embedding length: {len(vector)}")
    print(f"First 8 dims: {vector[:8]}")


@app.command(
    help="Use embedding models (direct client): https://learn.microsoft.com/en-us/azure/foundry/how-to/develop/langchain-models#use-embedding-models"
)
def embeddings_direct(
    text: Annotated[
        str,
        typer.Option(
            "--text",
            "-t",
            help="Text to embed",
        ),
    ] = DEFAULT_SETTINGS["embedding_text"],
    model: Annotated[
        str,
        typer.Option(
            "--model",
            "-m",
            help="Embedding model to use (e.g., 'text-embedding-3-small')",
        ),
    ] = DEFAULT_SETTINGS["embedding_model"],
):
    from langchain_azure_ai.embeddings import AzureAIOpenAIApiEmbeddingsModel

    # Use the resource-level OpenAI v1 endpoint instead of project_endpoint
    # because the project-scoped path does not currently serve embeddings.
    embed_model = AzureAIOpenAIApiEmbeddingsModel(
        endpoint=_resource_openai_v1_endpoint(),
        credential=DefaultAzureCredential(),
        model=model,
        api_version="preview",
    )
    vector = embed_model.embed_query(text)
    print(f"Embedding length: {len(vector)}")
    print(f"First 8 dims: {vector[:8]}")


@app.command(
    help="Example: Run similarity search with a vector store: https://learn.microsoft.com/en-us/azure/foundry/how-to/develop/langchain-models#example-run-similarity-search-with-a-vector-store"
)
def vector_store_search(
    query: Annotated[
        str,
        typer.Option(
            "--query",
            "-q",
            help="Query to run similarity search for",
        ),
    ] = "thud",
    k: Annotated[
        int,
        typer.Option(
            "--k",
            "-k",
            help="Number of top similar documents to return",
        ),
    ] = 1,
    model_string: Annotated[
        str,
        typer.Option(
            "--model",
            "-m",
            help="Embedding model to use (e.g., 'azure_ai:text-embedding-3-small')",
        ),
    ] = DEFAULT_EMBEDDING_MODEL_STRING,
):
    from langchain.embeddings import init_embeddings
    from langchain_core.documents import Document
    from langchain_core.vectorstores import InMemoryVectorStore

    # Override the project endpoint with the resource-level OpenAI v1 endpoint
    # because the project-scoped path does not currently serve embeddings.
    embed_model = init_embeddings(
        model_string,
        endpoint=_resource_openai_v1_endpoint(),
        credential=DefaultAzureCredential(),
        api_version="preview",
    )

    vector_store = InMemoryVectorStore(embed_model)

    documents = [
        Document(
            id="1",
            page_content="foo",
            metadata={"baz": "bar"},
        ),
        Document(
            id="2",
            page_content="thud",
            metadata={"bar": "baz"},
        ),
    ]

    vector_store.add_documents(documents=documents)

    results = vector_store.similarity_search(query=query, k=k)
    for doc in results:
        print(f"* {doc.page_content} [{doc.metadata}]")


if __name__ == "__main__":
    if not load_dotenv(override=True, verbose=True):
        logging.warning("No .env file found; using defaults")
    app()
