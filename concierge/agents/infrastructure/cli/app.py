"""Agents CLI.

Standalone Typer CLI for the shared agent runtime (``concierge.agents``).

The CLI lets you exercise registered agents directly — without going through
``cloud_agent``'s task queue or ``chat``'s conversation flow — which is handy
for smoke-testing new agents in isolation.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Any

import typer
from dotenv import load_dotenv

from concierge.agents.application.contracts import AgentRequest, AgentResponse
from concierge.agents.domain.agent_types import AgentType
from concierge.agents.domain.exceptions import AgentNotFoundError
from concierge.agents.infrastructure.registry_factory import get_agent_registry
from concierge.agents.infrastructure.tools import ImageGenerationResult, generate_image
from concierge.loggers import enable_verbose_logging, get_logger
from concierge.observability import bootstrap_from_env, disable_tracing, enable_mlflow, enable_tracing
from concierge.settings import get_agents_settings
from concierge.settings.agents_knowledge import get_agents_knowledge_settings

app = typer.Typer(add_completion=False, help="Agents CLI")
image_app = typer.Typer(add_completion=False, help="Image generation commands")
knowledge_app = typer.Typer(add_completion=False, help="Knowledge retrieval tool commands")
logger = get_logger("concierge.agents")


@app.callback()
def _bootstrap(
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
                "Enable MLflow autologging for LangChain / LangGraph runs and forward "
                "Microsoft Agent Framework OpenTelemetry spans to MLflow. "
                "See https://mlflow.org/docs/latest/genai/tracing/integrations/listing/microsoft-agent-framework/"
            ),
        ),
    ] = False,
) -> None:
    """Load ``.env`` and configure observability for the standalone agents CLI.

    The boot sequence mirrors the ``chat`` and ``cloud_agent`` CLIs so that
    ``--tracing`` / ``--mlflow`` / ``--verbose`` behave consistently across
    services. ``bootstrap_from_env`` is called first so that environment
    defaults (``CONCIERGE_TRACING_ENABLED`` / ``CONCIERGE_MLFLOW_ENABLED``)
    are applied before the explicit flag overrides.
    """
    load_dotenv()
    bootstrap_from_env("concierge-agents")
    if tracing:
        enable_tracing()
    else:
        disable_tracing()
    if verbose:
        enable_verbose_logging()
    if mlflow:
        enable_mlflow()


def _print_json(payload: object) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=False))


def _handle_error(exc: Exception) -> None:
    typer.echo(str(exc), err=True)
    raise typer.Exit(code=1) from exc


def _parse_json_option(raw: str, *, option_name: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        typer.echo(f"Invalid JSON for {option_name}: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    if not isinstance(value, dict):
        typer.echo(f"{option_name} must be a JSON object, got {type(value).__name__}", err=True)
        raise typer.Exit(code=1)
    return value


def _response_to_dict(response: AgentResponse) -> dict[str, object]:
    return {
        "status": response.status,
        "result": response.result,
        "error": response.error,
    }


def _image_result_to_dict(
    result: ImageGenerationResult,
    *,
    include_base64: bool,
) -> dict[str, Any]:
    payload = asdict(result)
    if not include_base64:
        for image in payload["images"]:
            image["b64_json"] = None
    return payload


@app.command("list")
def list_agents() -> None:
    """List registered agent type identifiers."""
    registry = get_agent_registry()
    _print_json(registry.list_agent_types())


@image_app.command("generate")
def image_generate(
    prompt: Annotated[str, typer.Option("--prompt", help="Prompt used to generate image(s)")],
    size: Annotated[str | None, typer.Option("--size", help="Image size")] = None,
    n: Annotated[int | None, typer.Option("--n", help="Number of images")] = None,
    output_dir: Annotated[
        str | None,
        typer.Option(
            "--output-dir",
            help="Output directory for .png files (default: ./generated_images)",
        ),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Print full JSON output")] = False,
    include_base64: Annotated[
        bool,
        typer.Option(
            "--include-base64",
            help="Include image base64 in --json output",
        ),
    ] = False,
) -> None:
    settings = get_agents_settings()
    resolved_size = size or settings.image_size
    resolved_n = n if n is not None else settings.image_n
    resolved_output_dir = str((Path(output_dir) if output_dir else Path.cwd() / "generated_images").resolve())

    try:
        result = asyncio.run(
            generate_image(
                prompt,
                size=resolved_size,
                n=resolved_n,
                save_dir=resolved_output_dir,
            )
        )
    except Exception as exc:
        _handle_error(exc)
        return

    payload = _image_result_to_dict(result, include_base64=include_base64)
    if json_output:
        _print_json(payload)
        return

    typer.echo(f"Generated {len(result.images)} image{'s' if len(result.images) != 1 else ''}:")
    for index, image in enumerate(payload["images"], start=1):
        typer.echo(f"  [{index}] {image['path']}")
        if image["revised_prompt"]:
            typer.echo(f"      revised_prompt: {image['revised_prompt']}")


@app.command("invoke")
def invoke_agent(
    agent_type: Annotated[str, typer.Option("--agent-type", help="Registered agent identifier")],
    payload: Annotated[
        str,
        typer.Option(
            "--payload",
            help="JSON object string used as AgentRequest.payload",
        ),
    ] = "{}",
    context: Annotated[
        str,
        typer.Option(
            "--context",
            help="JSON object string used as AgentRequest.context",
        ),
    ] = "{}",
    message: Annotated[
        str | None,
        typer.Option(
            "--message",
            help=("Shortcut that merges {'message': value} into --payload (all built-in agents read payload.message)"),
        ),
    ] = None,
) -> None:
    """Invoke a registered agent directly and print ``AgentResponse`` as JSON.

    ``--payload`` and ``--context`` accept JSON object strings.  ``--message``
    is a convenience shortcut that merges ``{"message": <value>}`` into the
    payload so the common case stays short:

    .. code-block:: bash

        agents-cli invoke --agent-type echo --message hello
    """
    parsed_payload = _parse_json_option(payload, option_name="--payload")
    parsed_context = _parse_json_option(context, option_name="--context")
    if message is not None:
        parsed_payload["message"] = message

    try:
        agent = get_agent_registry().resolve(agent_type)
    except AgentNotFoundError as exc:
        _handle_error(exc)
        return

    request = AgentRequest(
        agent_type=agent_type,
        payload=parsed_payload,
        context=parsed_context,
    )

    async def _run() -> AgentResponse:
        return await agent.handle(request)

    response = asyncio.run(_run())
    _print_json(_response_to_dict(response))
    if response.status != "succeeded":
        raise typer.Exit(code=1)


@app.command("info")
def agent_info(
    agent_type: Annotated[str, typer.Option("--agent-type", help="Registered agent identifier")],
) -> None:
    """Show metadata for a registered agent (class, module, relevant settings).

    Intentionally does not instantiate any LLM client — it only reports the
    Python class and the agent-level settings, which is useful to confirm
    that the configured ``AGENTS_LANGGRAPH_MODEL`` is what you expect before
    running an actual ``invoke``.
    """
    try:
        agent = get_agent_registry().resolve(agent_type)
    except AgentNotFoundError as exc:
        _handle_error(exc)
        return

    cls = agent.__class__
    info: dict[str, object] = {
        "agent_type": agent_type,
        "class": cls.__name__,
        "module": cls.__module__,
    }

    # Surface framework-specific settings when relevant. We read them from
    # the configured settings rather than introspecting private attributes
    # so the output stays stable regardless of how the agent was wired.
    if agent_type == AgentType.LANGGRAPH:
        agents_settings = get_agents_settings()
        info["settings"] = {
            "langgraph_model": agents_settings.langgraph_model,
            "langgraph_system_prompt": agents_settings.langgraph_system_prompt,
            "image_model": agents_settings.image_model,
            "image_size": agents_settings.image_size,
            "image_n": agents_settings.image_n,
            "image_api_version": agents_settings.image_api_version,
        }
    if agent_type == AgentType.GITHUB_COPILOT_SDK:
        agents_settings = get_agents_settings()
        info["settings"] = {
            "github_copilot_sdk_model": agents_settings.github_copilot_sdk_model,
            "github_copilot_sdk_system_prompt": agents_settings.github_copilot_sdk_system_prompt,
        }
    if agent_type == AgentType.MICROSOFT_AGENT_FRAMEWORK:
        agents_settings = get_agents_settings()
        info["settings"] = {
            "microsoft_agent_framework_model": agents_settings.microsoft_agent_framework_model,
            "microsoft_agent_framework_system_prompt": agents_settings.microsoft_agent_framework_system_prompt,
            "image_model": agents_settings.image_model,
            "image_size": agents_settings.image_size,
            "image_n": agents_settings.image_n,
            "image_api_version": agents_settings.image_api_version,
        }

    _print_json(info)


app.add_typer(image_app, name="image")


@knowledge_app.command("list")
def knowledge_list() -> None:
    """List env-configured knowledge retrieval tools."""
    settings = get_agents_knowledge_settings()
    payload = [
        {
            "name": config.name,
            "collection": config.collection,
            "description": config.description,
            "top_k": config.top_k,
            "max_chars": config.max_chars,
        }
        for config in settings.configured_tools()
    ]
    _print_json(payload)


app.add_typer(knowledge_app, name="knowledge")


if __name__ == "__main__":
    app()
