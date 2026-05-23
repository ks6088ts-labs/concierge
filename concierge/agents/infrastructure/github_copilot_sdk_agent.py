"""GitHub Copilot SDK based agent.

Drives a real Copilot session per request, mirroring the README example:
open a :class:`CopilotClient` context, ``create_session`` (also as an async
context manager), register an event handler, ``send`` the user's message,
and wait for :class:`SessionIdleData` before tearing the session down.

The assistant's final :class:`AssistantMessageData.content` is surfaced as
``AgentResponse.result["reply"]`` so this agent plugs into the rest of the
shared agent runtime (``cloud_agent`` worker, ``chat`` responder, the
``agents-cli`` invoke command) the same way the other built-in agents do.

Reference: https://raw.githubusercontent.com/github/copilot-sdk/refs/heads/main/python/README.md
"""

from __future__ import annotations

import asyncio
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


class GitHubCopilotSdkAgent:
    """GitHub Copilot SDK-backed agent.

    For every ``handle()`` call the agent:

    1. Builds a fresh :class:`CopilotClient` (no shared global state).
    2. Calls ``client.create_session`` with the configured model and
       ``system_prompt`` (injected via ``SystemMessageReplaceConfig``).
    3. Registers an event handler that captures
       :class:`AssistantMessageData.content` and signals completion on
       :class:`SessionIdleData`.
    4. Sends ``payload.message`` over the session, awaits idle, and
       returns the captured reply in :class:`AgentResponse`.

    :param model: Model forwarded to ``create_session(model=...)``
        (e.g. ``"gpt-5"``).
    :param system_prompt: System prompt forwarded to ``create_session`` as
        ``system_message={"mode": "replace", "content": ...}``.
    """

    agent_type: str = AgentType.GITHUB_COPILOT_SDK.value

    def __init__(
        self,
        model: str,
        system_prompt: str,
    ) -> None:
        self._model = model
        self._system_prompt = system_prompt

    async def handle(self, request: AgentRequest) -> AgentResponse:
        message = self._extract_message(request.payload)
        if not message:
            return AgentResponse(
                status="failed",
                error="payload.message is required (non-empty string)",
            )

        try:
            reply = await self._run_session(message)
        except Exception as exc:  # noqa: BLE001
            return AgentResponse(status="failed", error=f"{type(exc).__name__}: {exc}")

        return AgentResponse(
            status="succeeded",
            result={
                "message": message,
                "reply": reply,
                "model": self._model,
            },
        )

    # ------------------------------------------------------------------
    # SDK plumbing
    # ------------------------------------------------------------------

    async def _run_session(self, message: str) -> str:
        """Open a session, send ``message``, and return the assistant reply.

        Both the :class:`CopilotClient` and the returned session are used
        as async context managers so the CLI subprocess and the JSON-RPC
        session are torn down even when waiting raises. The handler
        accumulates ``AssistantMessageData.content`` chunks (the SDK may
        emit more than one final message per turn) and
        :class:`SessionIdleData` signals end-of-turn.
        """
        async with self._build_client() as client:
            session_cm = await client.create_session(
                on_permission_request=PermissionHandler.approve_all,
                model=self._model,
                system_message={"mode": "replace", "content": self._system_prompt},
            )
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
