from __future__ import annotations

import json

import httpx

from scripts.langgraph import vanilla


def _task_payload(task_id: str) -> dict[str, str]:
    return {
        "id": task_id,
        "title": "buy milk",
        "description": "whole",
        "status": "TODO",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }


def test_todo_tools_success_paths_and_payloads() -> None:
    seen: list[httpx.Request] = []
    task_id = "11111111-1111-1111-1111-111111111111"

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.method == "POST" and request.url.path == "/tasks":
            assert json.loads(request.content.decode()) == {"title": "buy milk", "description": "whole"}
            return httpx.Response(status_code=201, json=_task_payload(task_id))
        if request.method == "GET" and request.url.path == "/tasks":
            assert request.url.params.get("status") == "TODO"
            return httpx.Response(status_code=200, json=[_task_payload(task_id)])
        if request.method == "GET" and request.url.path == f"/tasks/{task_id}":
            return httpx.Response(status_code=200, json=_task_payload(task_id))
        if request.method == "PATCH" and request.url.path == f"/tasks/{task_id}":
            assert json.loads(request.content.decode()) == {"title": "buy eggs", "status": "IN_PROGRESS"}
            payload = _task_payload(task_id)
            payload["title"] = "buy eggs"
            payload["status"] = "IN_PROGRESS"
            return httpx.Response(status_code=200, json=payload)
        if request.method == "POST" and request.url.path == f"/tasks/{task_id}/complete":
            payload = _task_payload(task_id)
            payload["status"] = "DONE"
            return httpx.Response(status_code=200, json=payload)
        if request.method == "DELETE" and request.url.path == f"/tasks/{task_id}":
            return httpx.Response(status_code=204)
        return httpx.Response(status_code=404, json={"detail": "not found"})

    tools = {
        tool.name: tool
        for tool in vanilla._build_tools("http://test", timeout=3.0, transport=httpx.MockTransport(handler))
    }

    created = tools["create_task"].invoke({"title": "buy milk", "description": "whole"})
    assert created["id"] == task_id

    listed = tools["list_tasks"].invoke({"status": "todo"})
    assert isinstance(listed, list)
    assert listed[0]["id"] == task_id

    got = tools["get_task"].invoke({"task_id": task_id})
    assert got["id"] == task_id

    updated = tools["update_task"].invoke({"task_id": task_id, "title": "buy eggs", "status": "in_progress"})
    assert updated["title"] == "buy eggs"

    completed = tools["complete_task"].invoke({"task_id": task_id})
    assert completed["status"] == "DONE"

    deleted = tools["delete_task"].invoke({"task_id": task_id})
    assert deleted == {"deleted": True, "id": task_id}

    assert [request.method for request in seen] == ["POST", "GET", "GET", "PATCH", "POST", "DELETE"]


def test_tool_http_error_returns_error_dict() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=500, json={"detail": "internal"})

    tools = {
        tool.name: tool
        for tool in vanilla._build_tools("http://test", timeout=3.0, transport=httpx.MockTransport(handler))
    }

    result = tools["create_task"].invoke({"title": "x"})

    assert result["status_code"] == 500
    assert "internal" in result["error"]


def test_tool_connection_failure_returns_error_dict() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    tools = {
        tool.name: tool
        for tool in vanilla._build_tools("http://test", timeout=3.0, transport=httpx.MockTransport(handler))
    }

    result = tools["list_tasks"].invoke({})

    assert result["status_code"] == 0
    assert "ConnectError" in result["error"]
