"""Tests for cloud_agent in-memory task repository."""

from __future__ import annotations

import uuid

from concierge.cloud_agent.domain.entities import Task
from concierge.cloud_agent.domain.value_objects import TaskStatus
from concierge.cloud_agent.infrastructure.persistence.memory import InMemoryTaskRepository


def test_save_and_find_by_id() -> None:
    repo = InMemoryTaskRepository()
    task = Task(agent_type="echo", payload={"k": "v"})
    repo.save(task)
    found = repo.find_by_id(task.id)
    assert found is not None
    assert found.id == task.id
    assert found.agent_type == "echo"


def test_find_by_id_returns_none_for_missing() -> None:
    repo = InMemoryTaskRepository()
    assert repo.find_by_id(uuid.uuid4()) is None


def test_delete_existing() -> None:
    repo = InMemoryTaskRepository()
    task = Task(agent_type="echo", payload={})
    repo.save(task)
    assert repo.delete(task.id) is True
    assert repo.find_by_id(task.id) is None


def test_delete_missing_returns_false() -> None:
    repo = InMemoryTaskRepository()
    assert repo.delete(uuid.uuid4()) is False


def test_find_all_empty() -> None:
    repo = InMemoryTaskRepository()
    assert repo.find_all() == []


def test_find_all_returns_all() -> None:
    repo = InMemoryTaskRepository()
    repo.save(Task(agent_type="echo", payload={}))
    repo.save(Task(agent_type="other", payload={}))
    assert len(repo.find_all()) == 2


def test_find_all_status_filter() -> None:
    repo = InMemoryTaskRepository()
    t1 = Task(agent_type="echo", payload={})
    t2 = Task(agent_type="echo", payload={})
    t2.mark_running()
    t2.mark_succeeded({})
    repo.save(t1)
    repo.save(t2)
    queued = repo.find_all(status=TaskStatus.QUEUED)
    assert len(queued) == 1
    assert queued[0].id == t1.id


def test_find_all_agent_type_filter() -> None:
    repo = InMemoryTaskRepository()
    repo.save(Task(agent_type="echo", payload={}))
    repo.save(Task(agent_type="summarizer", payload={}))
    echo_tasks = repo.find_all(agent_type="echo")
    assert len(echo_tasks) == 1
    assert echo_tasks[0].agent_type == "echo"


def test_find_all_limit_offset() -> None:
    repo = InMemoryTaskRepository()
    for _ in range(5):
        repo.save(Task(agent_type="echo", payload={}))
    page1 = repo.find_all(limit=3, offset=0)
    page2 = repo.find_all(limit=3, offset=3)
    assert len(page1) == 3
    assert len(page2) == 2


def test_count() -> None:
    repo = InMemoryTaskRepository()
    repo.save(Task(agent_type="echo", payload={}))
    repo.save(Task(agent_type="echo", payload={}))
    assert repo.count() == 2
    assert repo.count(agent_type="echo") == 2
    assert repo.count(agent_type="other") == 0


def test_save_updates_existing() -> None:
    repo = InMemoryTaskRepository()
    task = Task(agent_type="echo", payload={"a": 1})
    repo.save(task)
    task.mark_running()
    repo.save(task)
    found = repo.find_by_id(task.id)
    assert found is not None
    assert found.status == TaskStatus.RUNNING
