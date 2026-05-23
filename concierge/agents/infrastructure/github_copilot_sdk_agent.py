"""GitHub Copilot SDK based agent.

Drives a real Copilot session per request, mirroring the README example:
open a :class:`CopilotClient` context, ``create_session`` (also as an async
context manager), register an event handler, ``send`` the user's message,
and wait for :class:`SessionIdleData` before tearing the session down.

The assistant's final :class:`AssistantMessageData.content` is surfaced as
``AgentResponse.result["reply"]`` so this agent plugs into the rest of the
shared agent runtime (``cloud_agent`` worker, ``chat`` responder, the
``agents-cli`` invoke command) the same way the other built-in agents do.

The agent can optionally be configured with a list of *tool builders*
(``Callable[[dict[str, Any]], Tool]``). Each builder is invoked once per
``handle()`` with a fresh ``side_outputs`` dict — mirroring the contract
used by :class:`LangGraphAgent` / :class:`MicrosoftAgentFrameworkAgent` —
and the returned :class:`copilot.tools.Tool` is passed to
``client.create_session(tools=...)`` so the Copilot CLI can dispatch tool
calls back into the Python process.

Reference: https://raw.githubusercontent.com/github/copilot-sdk/refs/heads/main/python/README.md
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from copilot import CopilotClient
from copilot.generated.session_events import (
    AssistantMessageData,
    SessionEvent,
    SessionIdleData,
)
from copilot.session import PermissionHandler

from concierge.agents.application.contracts import AgentRequest, AgentResponse
from concierge.agents.domain.agent_types import AgentType

CopilotSdkToolBuilder = Callable[[dict[str, Any]], Any]


class GitHubCopilotSdkAgent:
    """GitHub Copilot SDK-backed agent.

    For every ``handle()`` call the agent:

    1. Builds a fresh :class:`CopilotClient` (no shared global state).
    2. Builds each configured tool by calling its builder with a fresh
       ``side_outputs`` dict.
    3. Calls ``client.create_session`` with the configured model,
       ``system_prompt`` (injected via ``SystemMessageReplaceConfig``),
       the built tools, and an ``on_pre_tool_use`` hook that records
       tool-call ``{name, args}`` pairs.
    4. Registers an event handler that captures
       :class:`AssistantMessageData.content` and signals completion on
       :class:`SessionIdleData`.
    5. Sends ``payload.message`` over the session, awaits idle, and
       returns the captured reply, recorded tool calls, and any tool
       side outputs in :class:`AgentResponse`.

    :param model: Model forwarded to ``create_session(model=...)``
        (e.g. ``"gpt-5"``).
    :param system_prompt: System prompt forwarded to ``create_session`` as
        ``system_message={"mode": "replace", "content": ...}``.
    :param tool_builders: Optional list of tool builder callables. Each is
        invoked once per ``handle()`` with the per-request ``side_outputs``
        dict and must return a :class:`copilot.tools.Tool`.
    """

    agent_type: str = AgentType.GITHUB_COPILOT_SDK.value

    def __init__(
        self,
        model: str,
        system_prompt: str,
        tool_builders: list[CopilotSdkToolBuilder] | None = None,
    ) -> None:
        self._model = model
        self._system_prompt = system_prompt
        self._tool_builders: list[CopilotSdkToolBuilder] = list(tool_builders or [])

    async def handle(self, request: AgentRequest) -> AgentResponse:
        message = self._extract_message(request.payload)
        if not message:
            return AgentResponse(
                status="failed",
                error="payload.message is required (non-empty string)",
            )

        side_outputs: dict[str, Any] = {}
        tool_calls: list[dict[str, Any]] = []

        try:
            reply = await self._run_session(message, side_outputs, tool_calls)
        except Exception as exc:  # noqa: BLE001
            return AgentResponse(status="failed", error=f"{type(exc).__name__}: {exc}")

        response_result: dict[str, Any] = {
            "message": message,
            "reply": reply,
            "tool_calls": tool_calls,
            "model": self._model,
        }
        response_result.update(side_outputs)
        return AgentResponse(status="succeeded", result=response_result)

    # ------------------------------------------------------------------
    # SDK plumbing
    # ------------------------------------------------------------------

    async def _run_session(
        self,
        message: str,
        side_outputs: dict[str, Any],
        tool_calls: list[dict[str, Any]],
    ) -> str:
        """Open a session, send ``message``, and return the assistant reply.

        Both the :class:`CopilotClient` and the returned session are used
        as async context managers so the CLI subprocess and the JSON-RPC
        session are torn down even when waiting raises. The handler
        accumulates ``AssistantMessageData.content`` chunks (the SDK may
        emit more than one final message per turn) and
        :class:`SessionIdleData` signals end-of-turn.
        """
        tools = [builder(side_outputs) for builder in self._tool_builders]

        def on_pre_tool_use(input_data: dict[str, Any], _invocation: dict[str, str]) -> None:
            tool_calls.append(
                {
                    "name": input_data.get("toolName"),
                    "args": input_data.get("toolArgs"),
                }
            )
            return None

        create_kwargs: dict[str, Any] = {
            "on_permission_request": PermissionHandler.approve_all,
            "model": self._model,
            "system_message": {"mode": "replace", "content": self._system_prompt},
        }
        if tools:
            create_kwargs["tools"] = tools
            create_kwargs["hooks"] = {"on_pre_tool_use": on_pre_tool_use}

        async with self._build_client() as client:
            session_cm = await client.create_session(**create_kwargs)
            async with session_cm as session:
                done = asyncio.Event()
                reply_parts: list[str] = []

                def on_event(event: SessionEvent) -> None:
                    match event.data:
                        case AssistantMessageData() as data:
                            if data.content:
                                reply_parts.append(data.content)
                        case SessionIdleData():
                            done.set()

                session.on(on_event)
                await session.send(message)
                await done.wait()

                return "".join(reply_parts)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_message(payload: dict[str, Any]) -> str:
        value = payload.get("message")
        return value if isinstance(value, str) and value.strip() else ""

    @staticmethod
    def _build_client() -> CopilotClient:
        """Construct a fresh :class:`CopilotClient`.

        Isolated as a seam so unit tests can patch it to return a fake
        async-context-manager client without instantiating the real CLI
        subprocess.
        """
        return CopilotClient()
