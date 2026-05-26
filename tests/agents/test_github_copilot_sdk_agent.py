"""Unit tests for GitHubCopilotSdkAgent (shared agents package).

The Copilot SDK ``CopilotClient`` / ``CopilotSession`` chain is fully mocked
so the tests do not spawn the GitHub Copilot CLI subprocess.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from copilot.client import TelemetryConfig
from copilot.generated.session_events import AssistantMessageData, SessionEvent, SessionIdleData
from copilot.session import PermissionHandler

from concierge.agents.application.contracts import AgentRequest, AgentResponse
from concierge.agents.domain.agent_types import AgentType
from concierge.agents.infrastructure.github_copilot_sdk_agent import GitHubCopilotSdkAgent

_MODEL = "gpt-5"
_SYSTEM_PROMPT = "You are a minimal echo agent."


def _make_request(payload: dict[str, Any]) -> AgentRequest:
    return AgentRequest(
        agent_type=AgentType.GITHUB_COPILOT_SDK,
        payload=payload,
        context={"task_id": "00000000-0000-0000-0000-000000000001"},
    )


# ---------------------------------------------------------------------------
# Fake SDK doubles
# ---------------------------------------------------------------------------


def _make_event(data: object) -> SessionEvent:
    """Build a minimal SessionEvent that exposes the given ``data``.

    The agent's event handler only inspects ``event.data`` via ``match`` so
    we don't need a fully-populated SessionEvent — a SimpleNamespace-like
    stand-in is enough.
    """
    event = MagicMock(spec=SessionEvent)
    event.data = data
    return event


class _FakeSession:
    """Fake :class:`CopilotSession` async context manager.

    On ``send``, replays the configured event sequence through the
    registered handler so the agent's ``done.wait()`` resolves and the
    accumulated reply matches the supplied ``AssistantMessageData``
    contents.
    """

    def __init__(self, events: list[object]) -> None:
        self._events = events
        self._handler = None
        self.sent: list[str] = []

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    def on(self, handler):
        self._handler = handler
        return lambda: None

    async def send(self, prompt: str, **_kwargs) -> str:
        self.sent.append(prompt)
        assert self._handler is not None, "session.on must be called before send"
        for data in self._events:
            self._handler(_make_event(data))
        return "msg-id"


class _FakeClient:
    """Fake :class:`CopilotClient` async context manager."""

    def __init__(self, session: _FakeSession) -> None:
        self._session = session
        self.create_session_kwargs: dict[str, Any] | None = None

    async def __aenter__(self) -> _FakeClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def create_session(self, **kwargs: Any) -> _FakeSession:
        self.create_session_kwargs = kwargs
        return self._session


# ---------------------------------------------------------------------------
# Tests: _extract_message
# ---------------------------------------------------------------------------


def test_extract_message_returns_message_string() -> None:
    agent = GitHubCopilotSdkAgent.__new__(GitHubCopilotSdkAgent)
    assert agent._extract_message({"message": "hello"}) == "hello"


def test_extract_message_returns_empty_for_whitespace_only() -> None:
    agent = GitHubCopilotSdkAgent.__new__(GitHubCopilotSdkAgent)
    assert agent._extract_message({"message": "   "}) == ""


def test_extract_message_missing_key() -> None:
    agent = GitHubCopilotSdkAgent.__new__(GitHubCopilotSdkAgent)
    assert agent._extract_message({}) == ""


def test_extract_message_non_string_value() -> None:
    agent = GitHubCopilotSdkAgent.__new__(GitHubCopilotSdkAgent)
    assert agent._extract_message({"message": 42}) == ""  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Tests: handle()
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_handle_success_returns_session_reply() -> None:
    """Reply is the concatenation of AssistantMessageData.content chunks."""
    agent = GitHubCopilotSdkAgent(model=_MODEL, system_prompt=_SYSTEM_PROMPT)

    session = _FakeSession(
        events=[
            AssistantMessageData(content="Hello ", message_id="m1"),
            AssistantMessageData(content="Copilot", message_id="m2"),
            SessionIdleData(),
        ],
    )
    client = _FakeClient(session)

    with patch.object(agent, "_build_client", return_value=client):
        output: AgentResponse = await agent.handle(_make_request({"message": "Hello Copilot"}))

    assert output.status == "succeeded"
    assert output.result == {
        "message": "Hello Copilot",
        "reply": "Hello Copilot",
        "tool_calls": [],
        "model": _MODEL,
    }
    assert output.error is None
    # The fake session received the user message exactly once.
    assert session.sent == ["Hello Copilot"]
    # create_session was called with the configured model / system prompt /
    # the SDK approve-all permission helper.
    assert client.create_session_kwargs is not None
    assert client.create_session_kwargs["model"] == _MODEL
    assert client.create_session_kwargs["system_message"] == {
        "mode": "replace",
        "content": _SYSTEM_PROMPT,
    }
    assert client.create_session_kwargs["on_permission_request"] is PermissionHandler.approve_all
    # No tool builders configured -> tools / hooks must not be forwarded.
    assert "tools" not in client.create_session_kwargs
    assert "hooks" not in client.create_session_kwargs


@pytest.mark.anyio
async def test_handle_missing_message_returns_failed() -> None:
    agent = GitHubCopilotSdkAgent(model=_MODEL, system_prompt=_SYSTEM_PROMPT)

    output: AgentResponse = await agent.handle(_make_request({}))

    assert output.status == "failed"
    assert output.error == "payload.message is required (non-empty string)"


@pytest.mark.anyio
async def test_handle_sdk_initialization_error_returns_failed() -> None:
    """Errors raised while opening the session are captured in AgentResponse.error."""
    agent = GitHubCopilotSdkAgent(model=_MODEL, system_prompt=_SYSTEM_PROMPT)

    with patch.object(agent, "_build_client", side_effect=RuntimeError("sdk init failed")):
        output: AgentResponse = await agent.handle(_make_request({"message": "hello"}))

    assert output.status == "failed"
    assert output.error == "RuntimeError: sdk init failed"


@pytest.mark.anyio
async def test_handle_session_send_error_returns_failed() -> None:
    """Errors raised inside the session (e.g. ``send`` failure) are surfaced."""
    agent = GitHubCopilotSdkAgent(model=_MODEL, system_prompt=_SYSTEM_PROMPT)

    failing_session = AsyncMock()
    failing_session.__aenter__.return_value = failing_session
    failing_session.on = MagicMock(return_value=lambda: None)
    failing_session.send = AsyncMock(side_effect=RuntimeError("send failed"))

    client = AsyncMock()
    client.__aenter__.return_value = client
    client.create_session = AsyncMock(return_value=failing_session)

    with patch.object(agent, "_build_client", return_value=client):
        output: AgentResponse = await agent.handle(_make_request({"message": "hi"}))

    assert output.status == "failed"
    assert output.error is not None
    assert "RuntimeError" in output.error
    assert "send failed" in output.error


@pytest.mark.anyio
async def test_handle_empty_reply_chunks_returns_empty_reply() -> None:
    """An idle event with no AssistantMessageData yields an empty reply string."""
    agent = GitHubCopilotSdkAgent(model=_MODEL, system_prompt=_SYSTEM_PROMPT)

    session = _FakeSession(events=[SessionIdleData()])
    client = _FakeClient(session)

    with patch.object(agent, "_build_client", return_value=client):
        output: AgentResponse = await agent.handle(_make_request({"message": "hi"}))

    assert output.status == "succeeded"
    assert output.result == {
        "message": "hi",
        "reply": "",
        "tool_calls": [],
        "model": _MODEL,
    }


# ---------------------------------------------------------------------------
# Tests: tool_builders wiring (custom tools + on_pre_tool_use hook)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_handle_with_tool_builders_forwards_tools_and_hook() -> None:
    """``tool_builders`` results are forwarded as ``tools`` and the hook is registered."""

    built_tools: list[object] = []

    def fake_builder(side_outputs: dict[str, Any]) -> object:
        side_outputs["images"] = ["dummy-image"]
        tool = object()
        built_tools.append(tool)
        return tool

    agent = GitHubCopilotSdkAgent(
        model=_MODEL,
        system_prompt=_SYSTEM_PROMPT,
        tool_builders=[fake_builder],
    )

    session = _FakeSession(events=[AssistantMessageData(content="ok", message_id="m1"), SessionIdleData()])
    client = _FakeClient(session)

    with patch.object(agent, "_build_client", return_value=client):
        output: AgentResponse = await agent.handle(_make_request({"message": "hello"}))

    assert output.status == "succeeded"
    assert client.create_session_kwargs is not None
    # Tools list is forwarded as-is (one tool per builder).
    assert client.create_session_kwargs["tools"] == built_tools
    # The on_pre_tool_use hook is registered.
    hooks = client.create_session_kwargs["hooks"]
    assert "on_pre_tool_use" in hooks
    assert callable(hooks["on_pre_tool_use"])
    # Side outputs from the builder are merged into result.
    assert output.result is not None
    assert output.result["images"] == ["dummy-image"]
    assert output.result["tool_calls"] == []


@pytest.mark.anyio
async def test_on_pre_tool_use_hook_records_tool_calls() -> None:
    """Hook invocations record ``{name, args}`` into ``AgentResponse.result['tool_calls']``."""

    def fake_builder(_side_outputs: dict[str, Any]) -> object:
        return object()

    agent = GitHubCopilotSdkAgent(
        model=_MODEL,
        system_prompt=_SYSTEM_PROMPT,
        tool_builders=[fake_builder],
    )

    captured_hook: list[Any] = []

    class _HookingSession(_FakeSession):
        async def send(self, prompt: str, **_kwargs: Any) -> str:
            # Simulate the SDK firing the pre-tool-use hook before the LLM reply.
            captured_hook[0](
                {"toolName": "echo", "toolArgs": {"text": prompt}},
                {},
            )
            return await super().send(prompt)

    session = _HookingSession(events=[AssistantMessageData(content="done", message_id="m1"), SessionIdleData()])
    client = _FakeClient(session)

    # Capture the hook reference for the fake session to invoke.
    original_create_session = client.create_session

    async def spy_create_session(**kwargs: Any) -> Any:
        captured_hook.append(kwargs["hooks"]["on_pre_tool_use"])
        return await original_create_session(**kwargs)

    client.create_session = spy_create_session  # ty: ignore[invalid-assignment]

    with patch.object(agent, "_build_client", return_value=client):
        output: AgentResponse = await agent.handle(_make_request({"message": "hello"}))

    assert output.status == "succeeded"
    assert output.result is not None
    assert output.result["tool_calls"] == [{"name": "echo", "args": {"text": "hello"}}]


def test_registry_includes_github_copilot_sdk() -> None:
    from concierge.agents.infrastructure.registry_factory import get_agent_registry

    get_agent_registry.cache_clear()
    registry = get_agent_registry()
    assert AgentType.GITHUB_COPILOT_SDK in registry.list_agent_types()
    assert AgentType.ECHO in registry.list_agent_types()


def test_agent_type() -> None:
    assert GitHubCopilotSdkAgent.agent_type == AgentType.GITHUB_COPILOT_SDK


def test_build_client_without_telemetry_uses_default_constructor(monkeypatch) -> None:
    captured: dict[str, Any] = {}
    sentinel = object()

    def _fake_copilot_client(*args: Any, **kwargs: Any) -> object:
        captured["args"] = args
        captured["kwargs"] = kwargs
        return sentinel

    monkeypatch.setattr(
        "concierge.agents.infrastructure.github_copilot_sdk_agent.CopilotClient",
        _fake_copilot_client,
    )

    agent = GitHubCopilotSdkAgent(model=_MODEL, system_prompt=_SYSTEM_PROMPT, telemetry_factory=lambda: None)

    built = agent._build_client()

    assert built is sentinel
    assert captured == {"args": (), "kwargs": {}}


def test_build_client_with_telemetry_passes_subprocess_config(monkeypatch) -> None:
    captured: dict[str, Any] = {}
    telemetry: TelemetryConfig = {
        "otlp_endpoint": "http://127.0.0.1:5000",
        "source_name": "concierge.github-copilot-sdk",
        "capture_content": False,
    }
    sentinel = object()

    def _fake_subprocess_config(*, telemetry: TelemetryConfig) -> dict[str, Any]:
        captured["telemetry"] = telemetry
        return {"telemetry": telemetry}

    def _fake_copilot_client(*args: Any, **kwargs: Any) -> object:
        captured["args"] = args
        captured["kwargs"] = kwargs
        return sentinel

    monkeypatch.setattr(
        "concierge.agents.infrastructure.github_copilot_sdk_agent.SubprocessConfig",
        _fake_subprocess_config,
    )
    monkeypatch.setattr(
        "concierge.agents.infrastructure.github_copilot_sdk_agent.CopilotClient",
        _fake_copilot_client,
    )

    agent = GitHubCopilotSdkAgent(
        model=_MODEL,
        system_prompt=_SYSTEM_PROMPT,
        telemetry_factory=lambda: telemetry,
    )

    built = agent._build_client()

    assert built is sentinel
    assert captured["telemetry"] == telemetry
    assert captured["args"] == ()
    assert captured["kwargs"] == {"config": {"telemetry": telemetry}}
