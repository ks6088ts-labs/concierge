"""Tests for cloud_agent domain entities."""

from __future__ import annotations

from typing import Any, cast

import pytest

from concierge.agents.domain.agent_types import AgentType
from concierge.cloud_agent.domain.entities import Task
from concierge.cloud_agent.domain.exceptions import TaskStateError, TaskValidationError
from concierge.cloud_agent.domain.value_objects import TaskStatus


def test_task_defaults() -> None:
    task = Task(agent_type=AgentType.ECHO, payload={})
    assert task.status == TaskStatus.QUEUED
    assert task.retry_count == 0
    assert task.result is None
    assert task.error is None
    assert task.started_at is None
    assert task.finished_at is None


def test_task_validates_agent_type_empty() -> None:
    with pytest.raises(TaskValidationError):
        Task(agent_type="", payload={})


def test_task_validates_agent_type_too_long() -> None:
    with pytest.raises(TaskValidationError):
        Task(agent_type="a" * 101, payload={})


def test_task_validates_payload_not_dict() -> None:
    with pytest.raises(TaskValidationError):
        Task(agent_type=AgentType.ECHO, payload=cast("dict[str, Any]", "not-a-dict"))


def test_task_validates_payload_too_large() -> None:
    big_payload = {"data": "x" * (65 * 1024)}
    with pytest.raises(TaskValidationError, match="payload exceeds"):
        Task(agent_type=AgentType.ECHO, payload=big_payload)


def test_task_mark_running() -> None:
    task = Task(agent_type=AgentType.ECHO, payload={})
    task.mark_running()
    assert task.status == TaskStatus.RUNNING
    assert task.started_at is not None


def test_task_mark_succeeded() -> None:
    task = Task(agent_type=AgentType.ECHO, payload={})
    task.mark_running()
    task.mark_succeeded({"output": "ok"})
    assert task.status == TaskStatus.SUCCEEDED
    assert task.result == {"output": "ok"}
    assert task.finished_at is not None


def test_task_mark_failed() -> None:
    task = Task(agent_type=AgentType.ECHO, payload={})
    task.mark_running()
    task.mark_failed("something went wrong")
    assert task.status == TaskStatus.FAILED
    assert task.error == "something went wrong"


def test_task_mark_cancelled() -> None:
    task = Task(agent_type=AgentType.ECHO, payload={})
    task.mark_cancelled()
    assert task.status == TaskStatus.CANCELLED


def test_task_mark_dead_letter() -> None:
    task = Task(agent_type=AgentType.ECHO, payload={})
    task.mark_running()
    task.mark_failed("error")
    task.mark_dead_letter("max retries exceeded")
    assert task.status == TaskStatus.DEAD_LETTER


def test_task_invalid_transition_raises() -> None:
    task = Task(agent_type=AgentType.ECHO, payload={})
    task.mark_running()
    task.mark_succeeded({})
    with pytest.raises(TaskStateError):
        task.mark_running()


def test_task_bump_retry() -> None:
    task = Task(agent_type=AgentType.ECHO, payload={}, max_retries=2)
    assert task.should_retry()
    task.bump_retry()
    assert task.retry_count == 1
    assert task.should_retry()
    task.bump_retry()
    assert task.retry_count == 2
    assert task.should_retry()
    task.bump_retry()
    assert task.retry_count == 3
    assert not task.should_retry()


def test_task_status_transitions() -> None:
    assert TaskStatus.QUEUED.can_transition_to(TaskStatus.RUNNING)
    assert TaskStatus.QUEUED.can_transition_to(TaskStatus.CANCELLED)
    assert not TaskStatus.QUEUED.can_transition_to(TaskStatus.SUCCEEDED)
    assert TaskStatus.RUNNING.can_transition_to(TaskStatus.SUCCEEDED)
    assert TaskStatus.RUNNING.can_transition_to(TaskStatus.FAILED)
    assert TaskStatus.FAILED.can_transition_to(TaskStatus.QUEUED)
    assert TaskStatus.FAILED.can_transition_to(TaskStatus.DEAD_LETTER)
    assert not TaskStatus.SUCCEEDED.can_transition_to(TaskStatus.QUEUED)
    assert not TaskStatus.DEAD_LETTER.can_transition_to(TaskStatus.QUEUED)
