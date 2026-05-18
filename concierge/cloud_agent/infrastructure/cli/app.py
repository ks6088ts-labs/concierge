"""Cloud Agent CLI.

Provides commands for dispatching tasks, querying task status, and
running the background worker.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Annotated

import typer
from dotenv import load_dotenv

from concierge.agents.domain.exceptions import AgentNotFoundError
from concierge.agents.infrastructure.registry_factory import get_agent_registry
from concierge.cloud_agent.application.use_cases import (
    CancelTaskUseCase,
    DispatchTaskUseCase,
    GetTaskUseCase,
    ListTasksUseCase,
)
from concierge.cloud_agent.domain.entities import Task
from concierge.cloud_agent.domain.exceptions import (
    TaskNotFoundError,
    TaskStateError,
    TaskValidationError,
)
from concierge.cloud_agent.domain.value_objects import TaskStatus
from concierge.cloud_agent.infrastructure.persistence.factory import get_task_repository
from concierge.cloud_agent.infrastructure.queue.factory import get_task_queue
from concierge.loggers import enable_verbose_logging, get_logger
from concierge.observability import bootstrap_from_env, disable_tracing, enable_mlflow, enable_tracing

app = typer.Typer(add_completion=False, help="Cloud Agent CLI")
task_app = typer.Typer(help="Task commands")
app.add_typer(task_app, name="task")
logger = get_logger("concierge.cloud_agent")


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
                "Enable MLflow autologging for LangChain / LangGraph runs. "
                "See https://mlflow.org/docs/latest/genai/tracing/integrations/listing/langgraph/"
            ),
        ),
    ] = False,
) -> None:
    load_dotenv()
    bootstrap_from_env("concierge-cloud-agent")
    if tracing:
        enable_tracing()
    else:
        disable_tracing()
    if verbose:
        enable_verbose_logging()
    if mlflow:
        enable_mlflow()


def _task_to_dict(task: Task) -> dict[str, object]:
    return {
        "id": str(task.id),
        "agent_type": task.agent_type,
        "status": task.status.value,
        "retry_count": task.retry_count,
        "max_retries": task.max_retries,
        "result": task.result,
        "error": task.error,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
    }


def _print_task(task: Task) -> None:
    typer.echo(json.dumps(_task_to_dict(task), ensure_ascii=False))


def _handle_error(exc: Exception) -> None:
    typer.echo(str(exc), err=True)
    raise typer.Exit(code=1) from exc


@task_app.command("dispatch")
def dispatch_task(
    agent_type: Annotated[str, typer.Option("--agent-type", help="Agent type identifier")],
    payload: Annotated[str, typer.Option("--payload", help="JSON payload string")] = "{}",
    max_retries: Annotated[int | None, typer.Option("--max-retries", help="Override max retries")] = None,
) -> None:
    """Dispatch a new task to the queue."""
    try:
        parsed_payload = json.loads(payload)
    except json.JSONDecodeError as exc:
        typer.echo(f"Invalid JSON payload: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    repository = get_task_repository()
    queue = get_task_queue()

    async def _run() -> Task:
        return await DispatchTaskUseCase(repository, queue).execute(
            agent_type=agent_type,
            payload=parsed_payload,
            max_retries=max_retries,
        )

    try:
        task = asyncio.run(_run())
        _print_task(task)
    except (TaskValidationError, AgentNotFoundError) as exc:
        _handle_error(exc)


@task_app.command("get")
def get_task(task_id: uuid.UUID) -> None:
    """Get a task by ID."""
    repository = get_task_repository()
    try:
        task = GetTaskUseCase(repository).execute(task_id)
        _print_task(task)
    except TaskNotFoundError as exc:
        _handle_error(exc)


@task_app.command("list")
def list_tasks(
    status: Annotated[TaskStatus | None, typer.Option("--status", help="Filter by status")] = None,
    agent_type: Annotated[str | None, typer.Option("--agent-type", help="Filter by agent type")] = None,
    limit: Annotated[int, typer.Option("--limit", help="Max results")] = 100,
    offset: Annotated[int, typer.Option("--offset", help="Offset")] = 0,
) -> None:
    """List tasks with optional filters."""
    repository = get_task_repository()
    tasks = ListTasksUseCase(repository).execute(
        status=status,
        agent_type=agent_type,
        limit=limit,
        offset=offset,
    )
    typer.echo(json.dumps([_task_to_dict(t) for t in tasks], ensure_ascii=False))


@task_app.command("cancel")
def cancel_task(task_id: uuid.UUID) -> None:
    """Cancel a queued task."""
    repository = get_task_repository()
    try:
        task = CancelTaskUseCase(repository).execute(task_id)
        _print_task(task)
    except (TaskNotFoundError, TaskStateError) as exc:
        _handle_error(exc)


@app.command("worker")
def run_worker(
    max_iterations: Annotated[
        int | None, typer.Option("--max-iterations", help="Stop after N iterations (testing)")
    ] = None,
) -> None:
    """Run the background worker loop."""
    from concierge.cloud_agent.infrastructure.cli.worker import run_worker as _run_worker

    asyncio.run(_run_worker(max_iterations=max_iterations))


@app.command("agents")
def list_agents() -> None:
    """List registered agent types."""
    registry = get_agent_registry()
    typer.echo(json.dumps(registry.list_agent_types(), ensure_ascii=False))


if __name__ == "__main__":
    app()
