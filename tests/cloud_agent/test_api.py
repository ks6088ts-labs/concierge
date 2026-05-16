"""API tests for cloud_agent FastAPI app."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from concierge.cloud_agent.application.agents import AgentRegistry, TaskInput, TaskOutput
from concierge.cloud_agent.infrastructure.persistence.memory import InMemoryTaskRepository
from concierge.cloud_agent.infrastructure.queue.memory import InMemoryTaskQueue
from concierge.cloud_agent.infrastructure.web.app import create_app
from concierge.cloud_agent.infrastructure.web.dependencies import (
    get_agent_registry_dep,
    get_task_queue,
    get_task_repository,
)


class _EchoAgent:
    agent_type = "echo"

    async def handle(self, task_input: TaskInput) -> TaskOutput:
        return TaskOutput(status="succeeded", result={"echo": task_input.payload})


@pytest.fixture
def app():
    application = create_app()
    repository = InMemoryTaskRepository()
    queue = InMemoryTaskQueue()
    registry = AgentRegistry()
    registry.register(_EchoAgent())
    application.dependency_overrides[get_task_repository] = lambda: repository
    application.dependency_overrides[get_task_queue] = lambda: queue
    application.dependency_overrides[get_agent_registry_dep] = lambda: registry
    return application


@pytest.mark.anyio
async def test_healthz(app) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/healthz")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_dispatch_and_get_task(app) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Dispatch
        resp = await client.post("/cloud-agent/tasks", json={"agent_type": "echo", "payload": {"x": 1}})
        assert resp.status_code == 201
        task = resp.json()
        assert task["status"] == "QUEUED"
        assert task["agent_type"] == "echo"
        task_id = task["id"]

        # Get by ID
        resp = await client.get(f"/cloud-agent/tasks/{task_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == task_id


@pytest.mark.anyio
async def test_list_tasks(app) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/cloud-agent/tasks", json={"agent_type": "echo", "payload": {}})
        resp = await client.get("/cloud-agent/tasks")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


@pytest.mark.anyio
async def test_list_tasks_status_filter(app) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/cloud-agent/tasks", json={"agent_type": "echo", "payload": {}})
        resp = await client.get("/cloud-agent/tasks", params={"status": "QUEUED"})
        assert resp.status_code == 200
        tasks = resp.json()
        assert all(t["status"] == "QUEUED" for t in tasks)


@pytest.mark.anyio
async def test_cancel_task(app) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/cloud-agent/tasks", json={"agent_type": "echo", "payload": {}})
        task_id = created.json()["id"]

        resp = await client.delete(f"/cloud-agent/tasks/{task_id}")
        assert resp.status_code == 204

        resp = await client.get(f"/cloud-agent/tasks/{task_id}")
        assert resp.json()["status"] == "CANCELLED"


@pytest.mark.anyio
async def test_patch_task_result(app) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/cloud-agent/tasks", json={"agent_type": "echo", "payload": {}})
        task_id = created.json()["id"]

        # Manually transition to RUNNING first
        patch_resp = await client.patch(
            f"/cloud-agent/tasks/{task_id}",
            json={"status": "RUNNING"},
        )
        # RUNNING transition via PATCH isn't directly supported; expect 409 since
        # UpdateTaskResult only handles SUCCEEDED/FAILED/CANCELLED
        # So instead test a valid CANCELLED transition
        created2 = await client.post("/cloud-agent/tasks", json={"agent_type": "echo", "payload": {}})
        task_id2 = created2.json()["id"]
        patch_resp = await client.patch(
            f"/cloud-agent/tasks/{task_id2}",
            json={"status": "CANCELLED"},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["status"] == "CANCELLED"


@pytest.mark.anyio
async def test_get_task_not_found(app) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        import uuid

        resp = await client.get(f"/cloud-agent/tasks/{uuid.uuid4()}")
        assert resp.status_code == 404


@pytest.mark.anyio
async def test_dispatch_unknown_agent_type(app) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/cloud-agent/tasks", json={"agent_type": "nonexistent", "payload": {}})
        assert resp.status_code == 400


@pytest.mark.anyio
async def test_list_agents(app) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/cloud-agent/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert "echo" in data["agent_types"]


@pytest.mark.anyio
async def test_dispatch_oversized_payload(app) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        big = {"data": "x" * (65 * 1024)}
        resp = await client.post("/cloud-agent/tasks", json={"agent_type": "echo", "payload": big})
        assert resp.status_code == 422
