from __future__ import annotations

from fastapi.testclient import TestClient
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from concierge.todo.infrastructure.web.app import create_app


def test_web_api_supports_crud_flow():
    client = TestClient(create_app())

    create_response = client.post("/tasks", json={"title": "Buy milk", "description": "2 bottles"})
    assert create_response.status_code == 201
    created = create_response.json()
    task_id = created["id"]
    assert created["status"] == "TODO"

    assert client.get(f"/tasks/{task_id}").json()["title"] == "Buy milk"
    assert client.get("/tasks", params={"status_filter": "TODO"}).json()["tasks"][0]["id"] == task_id

    updated = client.patch(f"/tasks/{task_id}", json={"status": "IN_PROGRESS"}).json()
    assert updated["status"] == "IN_PROGRESS"

    completed = client.post(f"/tasks/{task_id}/complete")
    assert completed.status_code == 200
    assert completed.json()["status"] == "DONE"

    deleted = client.delete(f"/tasks/{task_id}")
    assert deleted.status_code == 204
    assert client.get(f"/tasks/{task_id}").status_code == 404


def test_web_api_records_opentelemetry_spans():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    client = TestClient(create_app(tracer_provider=provider))

    response = client.get("/healthz")

    assert response.status_code == 200
    assert any("healthz" in span.name.lower() for span in exporter.get_finished_spans())
