from __future__ import annotations

import logging
import uuid
from typing import Any

from concierge.agents.domain.exceptions import AgentNotFoundError
from concierge.cloud_agent.application.agents import AgentRegistry, AgentRequest
from concierge.cloud_agent.application.queues import TaskQueue
from concierge.cloud_agent.application.repositories import TaskRepository
from concierge.cloud_agent.domain.entities import Task
from concierge.cloud_agent.domain.exceptions import TaskNotFoundError, TaskStateError
from concierge.cloud_agent.domain.value_objects import TaskStatus

logger = logging.getLogger(__name__)


class DispatchTaskUseCase:
    """Create a task and enqueue it for processing."""

    def __init__(self, repository: TaskRepository, queue: TaskQueue, max_retries: int = 3) -> None:
        self.repository = repository
        self.queue = queue
        self.max_retries = max_retries

    async def execute(
        self,
        agent_type: str,
        payload: dict[str, Any],
        max_retries: int | None = None,
    ) -> Task:
        task = Task(
            agent_type=agent_type,
            payload=payload,
            max_retries=max_retries if max_retries is not None else self.max_retries,
        )
        saved = self.repository.save(task)
        await self.queue.enqueue(saved.id)
        logger.info("Dispatched task id=%s agent_type=%s", saved.id, agent_type)
        return saved


class GetTaskUseCase:
    def __init__(self, repository: TaskRepository) -> None:
        self.repository = repository

    def execute(self, task_id: uuid.UUID) -> Task:
        task = self.repository.find_by_id(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        return task


class ListTasksUseCase:
    def __init__(self, repository: TaskRepository) -> None:
        self.repository = repository

    def execute(
        self,
        status: TaskStatus | None = None,
        agent_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Task]:
        return self.repository.find_all(status=status, agent_type=agent_type, limit=limit, offset=offset)


class CancelTaskUseCase:
    """Cancel a QUEUED task (best-effort for RUNNING)."""

    def __init__(self, repository: TaskRepository) -> None:
        self.repository = repository

    def execute(self, task_id: uuid.UUID) -> Task:
        task = self.repository.find_by_id(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        if task.status in (TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.DEAD_LETTER):
            raise TaskStateError(f"Cannot cancel task in status {task.status}")
        task.mark_cancelled()
        saved = self.repository.save(task)
        logger.info("Cancelled task id=%s", task_id)
        return saved


class UpdateTaskResultUseCase:
    """Update a task with the worker's result (internal use)."""

    def __init__(self, repository: TaskRepository) -> None:
        self.repository = repository

    def execute(
        self,
        task_id: uuid.UUID,
        status: TaskStatus,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> Task:
        task = self.repository.find_by_id(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        if status == TaskStatus.SUCCEEDED:
            task.mark_succeeded(result or {})
        elif status == TaskStatus.FAILED:
            task.mark_failed(error or "unknown error")
        elif status == TaskStatus.CANCELLED:
            task.mark_cancelled()
        else:
            raise TaskStateError(f"UpdateTaskResult does not support status {status}")
        saved = self.repository.save(task)
        logger.info("Updated task id=%s status=%s", task_id, status)
        return saved


class ProcessNextTaskUseCase:
    """Dequeue one message and run the corresponding agent."""

    def __init__(
        self,
        repository: TaskRepository,
        queue: TaskQueue,
        registry: AgentRegistry,
        visibility_timeout: int = 60,
    ) -> None:
        self.repository = repository
        self.queue = queue
        self.registry = registry
        self.visibility_timeout = visibility_timeout

    async def execute(self) -> bool:
        """Process one queued task. Returns True if a task was processed."""
        message = await self.queue.dequeue(visibility_timeout=self.visibility_timeout)
        if message is None:
            return False

        task = self.repository.find_by_id(message.task_id)
        if task is None:
            logger.warning("Dequeued message for unknown task id=%s; acking to discard", message.task_id)
            await self.queue.ack(message)
            return True

        if task.status == TaskStatus.CANCELLED:
            logger.info("Task id=%s is cancelled; discarding message", task.id)
            await self.queue.ack(message)
            return True

        # Mark RUNNING
        try:
            task.mark_running()
            self.repository.save(task)
        except TaskStateError:
            logger.warning("Task id=%s cannot be marked RUNNING (status=%s); acking", task.id, task.status)
            await self.queue.ack(message)
            return True

        # Resolve agent
        try:
            agent = self.registry.resolve(task.agent_type)
        except AgentNotFoundError:
            logger.error("Agent %r not registered for task id=%s", task.agent_type, task.id)
            task.mark_failed(f"Agent not registered: {task.agent_type!r}")
            task.bump_retry()
            if task.should_retry():
                self.repository.save(task)
                # Re-queue via failed->queued transition
                task2 = self.repository.find_by_id(task.id)
                if task2:
                    task2.status = TaskStatus.QUEUED
                    self.repository.save(task2)
                    await self.queue.enqueue(task.id)
                await self.queue.ack(message)
            else:
                task.mark_dead_letter(f"Agent not registered: {task.agent_type!r}")
                self.repository.save(task)
                await self.queue.move_to_dlq(message, reason=f"Agent not registered: {task.agent_type!r}")
            return True

        # Execute agent
        request = AgentRequest(
            agent_type=task.agent_type,
            payload=task.payload,
            context={"task_id": str(task.id)},
        )
        try:
            response = await agent.handle(request)
            if response.status == "succeeded":
                task.mark_succeeded(response.result or {})
                self.repository.save(task)
                await self.queue.ack(message)
                logger.info("Task id=%s succeeded", task.id)
            else:
                task.mark_failed(response.error or "agent returned failed status")
                task.bump_retry()
                if task.should_retry():
                    task.status = TaskStatus.QUEUED
                    self.repository.save(task)
                    await self.queue.enqueue(task.id)
                    await self.queue.ack(message)
                    logger.info("Task id=%s failed; re-queued (retry %d)", task.id, task.retry_count)
                else:
                    task.mark_dead_letter(response.error or "max retries exceeded")
                    self.repository.save(task)
                    await self.queue.move_to_dlq(message, reason=response.error or "max retries exceeded")
                    logger.warning("Task id=%s moved to DLQ", task.id)
        except Exception as exc:
            error_msg = str(exc)
            logger.exception("Unhandled exception processing task id=%s", task.id)
            task.mark_failed(error_msg)
            task.bump_retry()
            if task.should_retry():
                task.status = TaskStatus.QUEUED
                self.repository.save(task)
                await self.queue.enqueue(task.id)
                await self.queue.ack(message)
            else:
                task.mark_dead_letter(error_msg)
                self.repository.save(task)
                await self.queue.move_to_dlq(message, reason=error_msg)
        return True
