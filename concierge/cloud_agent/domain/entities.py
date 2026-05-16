from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from concierge.cloud_agent.domain.exceptions import TaskStateError, TaskValidationError
from concierge.cloud_agent.domain.value_objects import TaskStatus

_MAX_PAYLOAD_BYTES = 64 * 1024  # 64 KiB


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Task:
    agent_type: str
    payload: dict[str, Any]
    status: TaskStatus = TaskStatus.QUEUED
    result: dict[str, Any] | None = None
    error: str | None = None
    retry_count: int = 0
    max_retries: int = 3
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
    started_at: datetime | None = None
    finished_at: datetime | None = None

    def __post_init__(self) -> None:
        self._validate_agent_type(self.agent_type)
        self._validate_payload(self.payload)
        if self.retry_count < 0:
            raise TaskValidationError("retry_count must be >= 0")
        if self.max_retries < 0:
            raise TaskValidationError("max_retries must be >= 0")

    def transition_to(self, new_status: TaskStatus) -> None:
        """Transition to *new_status*, raising TaskStateError if not allowed."""
        if not self.status.can_transition_to(new_status):
            raise TaskStateError(f"Cannot transition from {self.status} to {new_status}")
        now = _utcnow()
        if new_status == TaskStatus.RUNNING:
            self.started_at = now
        elif new_status in (TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.DEAD_LETTER):
            self.finished_at = now
        self.status = new_status
        self.updated_at = now

    def mark_running(self) -> None:
        self.transition_to(TaskStatus.RUNNING)

    def mark_succeeded(self, result: dict[str, Any]) -> None:
        self.result = result
        self.transition_to(TaskStatus.SUCCEEDED)

    def mark_failed(self, error: str) -> None:
        self.error = error
        self.transition_to(TaskStatus.FAILED)
        self.updated_at = _utcnow()

    def mark_cancelled(self) -> None:
        self.transition_to(TaskStatus.CANCELLED)

    def mark_dead_letter(self, reason: str) -> None:
        self.error = reason
        if self.status == TaskStatus.FAILED:
            self.transition_to(TaskStatus.DEAD_LETTER)
        else:
            raise TaskStateError(f"Cannot move to DEAD_LETTER from {self.status}")

    def bump_retry(self) -> None:
        """Increment retry_count and re-queue if under max_retries, else dead-letter."""
        self.retry_count += 1
        self.updated_at = _utcnow()

    def should_retry(self) -> bool:
        return self.retry_count <= self.max_retries

    @staticmethod
    def _validate_agent_type(agent_type: str) -> None:
        if not 1 <= len(agent_type) <= 100:
            raise TaskValidationError("agent_type must be between 1 and 100 characters")

    @staticmethod
    def _validate_payload(payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict):
            raise TaskValidationError("payload must be a dict")
        import json

        encoded = json.dumps(payload).encode("utf-8")
        if len(encoded) > _MAX_PAYLOAD_BYTES:
            raise TaskValidationError(f"payload exceeds {_MAX_PAYLOAD_BYTES} bytes")
