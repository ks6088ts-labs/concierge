"""CLI worker for cloud_agent.

Polls the task queue and processes tasks using the registered agents.
"""

from __future__ import annotations

import asyncio
import signal

from concierge.cloud_agent.application.use_cases import ProcessNextTaskUseCase
from concierge.cloud_agent.infrastructure.agents.registry import get_agent_registry
from concierge.cloud_agent.infrastructure.persistence.factory import get_task_repository
from concierge.cloud_agent.infrastructure.queue.factory import get_task_queue
from concierge.loggers import get_logger
from concierge.settings import get_cloud_agent_settings

logger = get_logger("concierge.cloud_agent.worker")


async def run_worker(*, max_iterations: int | None = None) -> None:
    """Run the worker loop.

    Args:
        max_iterations: If set, stop after this many iterations (useful for tests).
    """
    settings = get_cloud_agent_settings()
    repository = get_task_repository()
    queue = get_task_queue()
    registry = get_agent_registry()

    use_case = ProcessNextTaskUseCase(
        repository=repository,
        queue=queue,
        registry=registry,
        visibility_timeout=settings.visibility_timeout_seconds,
    )

    shutdown = asyncio.Event()

    def _handle_signal(sig: int, _frame: object) -> None:  # pragma: no cover
        logger.info("Received signal %s; shutting down gracefully", sig)
        shutdown.set()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    logger.info("Worker started (poll_interval=%.1fs)", settings.poll_interval_seconds)
    iteration = 0
    while not shutdown.is_set():
        processed = await use_case.execute()
        if not processed:
            try:
                await asyncio.wait_for(
                    asyncio.shield(asyncio.sleep(settings.poll_interval_seconds)),
                    timeout=settings.poll_interval_seconds + 1,
                )
            except asyncio.TimeoutError:
                pass
        iteration += 1
        if max_iterations is not None and iteration >= max_iterations:
            break

    logger.info("Worker stopped")


def main() -> None:  # pragma: no cover
    asyncio.run(run_worker())


if __name__ == "__main__":  # pragma: no cover
    main()
