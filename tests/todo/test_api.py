from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from concierge.todo.infrastructure.persistence.memory import InMemoryTaskRepository
from concierge.todo.infrastructure.web.app import create_app
from concierge.todo.infrastructure.web.dependencies import get_task_repository


@pytest.fixture
def app():
    app = create_app()
    repository = InMemoryTaskRepository()
    app.dependency_overrides[get_task_repository] = lambda: repository
    return app


@pytest.mark.anyio
async def test_api_endpoints(app) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        health = await client.get("/healthz")
        assert health.status_code == 200
        assert health.json() == {"status": "ok"}

        created = await client.post("/tasks", json={"title": "buy milk", "description": "whole"})
        assert created.status_code == 201
        task = created.json()

        listed = await client.get("/tasks")
        assert listed.status_code == 200
        assert len(listed.json()) == 1

        got = await client.get(f"/tasks/{task['id']}")
        assert got.status_code == 200

        updated = await client.patch(f"/tasks/{task['id']}", json={"title": "buy eggs", "status": "IN_PROGRESS"})
        assert updated.status_code == 200
        assert updated.json()["title"] == "buy eggs"

        completed = await client.post(f"/tasks/{task['id']}/complete")
        assert completed.status_code == 200
        assert completed.json()["status"] == "DONE"

        filtered = await client.get("/tasks", params={"status": "DONE"})
        assert filtered.status_code == 200
        assert len(filtered.json()) == 1

        deleted = await client.delete(f"/tasks/{task['id']}")
        assert deleted.status_code == 204

        missing = await client.get(f"/tasks/{task['id']}")
        assert missing.status_code == 404


@pytest.mark.anyio
async def test_api_validation(app) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/tasks", json={"title": ""})
        assert response.status_code == 422


def test_create_app_with_observability_env(monkeypatch) -> None:
    monkeypatch.setenv("CONCIERGE_TRACING_ENABLED", "true")
    monkeypatch.setenv("CONCIERGE_MLFLOW_ENABLED", "false")

    app = create_app()

    assert app.title == "Todo API"
