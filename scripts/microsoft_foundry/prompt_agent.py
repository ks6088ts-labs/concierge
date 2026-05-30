"""CLI smoke-test script for Microsoft Foundry Agent Service (Prompt Agent).

Usage::

    uv run python -m scripts.microsoft_foundry.prompt_agent invoke --message "What is the size of France?"

Requires:
- ``AZURE_AI_PROJECT_ENDPOINT`` set (or in ``.env``)
- ``DefaultAzureCredential``-compatible authentication (``az login`` etc.)
- ``azure-ai-projects>=2.0.0`` installed
"""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated

import typer
from dotenv import load_dotenv

from concierge.agents.application.contracts import AgentRequest, AgentResponse
from concierge.agents.domain.agent_types import AgentType
from concierge.agents.infrastructure.foundry_agent_service_agent import FoundryAgentServiceAgent
from concierge.loggers import get_logger
from concierge.settings import get_microsoft_foundry_settings
from concierge.settings.agents import get_agents_settings

app = typer.Typer(
    add_completion=False,
    help="Foundry Agent Service (Prompt Agent) smoke-test CLI",
)

logger = get_logger(__name__)


@app.callback()
def _global_options(
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose (DEBUG) logging",
        ),
    ] = False,
) -> None:
    """Foundry Agent Service CLI - global options applied to every subcommand."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
        logger.setLevel(logging.DEBUG)


@app.command(help="Invoke the Foundry Agent Service with a message and print the response.")
def invoke(
    message: Annotated[
        str,
        typer.Option(
            "--message",
            "-m",
            help="Message to send to the Foundry Agent Service",
        ),
    ] = "Hello, how are you doing today?",
) -> None:
    """Send a message to the Foundry Agent Service and print the reply."""
    settings = get_agents_settings()
    foundry_settings = get_microsoft_foundry_settings()

    agent = FoundryAgentServiceAgent(
        project_endpoint=foundry_settings.azure_ai_project_endpoint,
        model=settings.foundry_agent_service_model,
        system_prompt=settings.foundry_agent_service_system_prompt,
        agent_name=settings.foundry_agent_service_agent_name,
    )

    request = AgentRequest(
        agent_type=AgentType.FOUNDRY_AGENT_SERVICE.value,
        payload={"message": message},
    )

    async def _run() -> AgentResponse:
        return await agent.handle(request)

    response = asyncio.run(_run())

    if response.status == "succeeded" and response.result:
        typer.echo(f"Reply: {response.result.get('reply', '')}")
        typer.echo(f"Model: {response.result.get('model', '')}")
        typer.echo(f"Agent: {response.result.get('agent_name', '')}")
    else:
        typer.echo(f"Error: {response.error}", err=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    if not load_dotenv(override=True, verbose=True):
        logging.warning("No .env file found; using defaults")
    app()
