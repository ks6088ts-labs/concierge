"""LangGraph-based echo agent.

Minimal LangChain ``create_agent`` agent that exposes a single ``echo`` tool.
It serves as the reference pattern for adding LangChain / LangGraph agents to
the ``cloud_agent`` service.
"""

from __future__ import annotations

from typing import Any, ClassVar

from azure.identity import DefaultAzureCredential
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage
from langchain_core.tools import tool

from concierge.cloud_agent.application.agents import TaskInput, TaskOutput
from concierge.settings import get_cloud_agent_settings


class LangGraphEchoAgent:
    """LangChain ``create_agent``-based minimal agent.

    ``TaskInput.payload["message"]`` is forwarded to the LLM.  The LLM calls
    the ``echo`` tool with the user text verbatim, and the final AI message
    together with the tool-call history are returned in ``TaskOutput.result``.

    The agent is instantiated (``_build_agent``) fresh on every ``handle()``
    call so that Azure credential acquisition does not block worker startup
    when the Foundry endpoint is not yet configured.
    """

    agent_type: ClassVar[str] = "langgraph-echo"

    def __init__(self) -> None:
        self._settings = get_cloud_agent_settings()

    async def handle(self, task_input: TaskInput) -> TaskOutput:
        message = self._extract_message(task_input.payload)
        if not message:
            return TaskOutput(
                status="failed",
                error="payload.message is required (non-empty string)",
            )

        try:
            agent = self._build_agent()
            result = await agent.ainvoke({"messages": [("user", message)]})
        except Exception as exc:  # noqa: BLE001
            return TaskOutput(status="failed", error=f"{type(exc).__name__}: {exc}")

        messages = result.get("messages", []) if isinstance(result, dict) else []
        final_text = self._final_text(messages)
        tool_calls = self._collect_tool_calls(messages)

        return TaskOutput(
            status="succeeded",
            result={
                "echo": message,
                "reply": final_text,
                "tool_calls": tool_calls,
            },
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_message(payload: dict[str, Any]) -> str:
        value = payload.get("message")
        return value if isinstance(value, str) and value.strip() else ""

    def _build_agent(self):
        chat_model = init_chat_model(
            self._settings.langgraph_model,
            credential=DefaultAzureCredential(),
        )

        @tool
        def echo(text: str) -> str:
            """Echo back the given text exactly."""
            return text

        return create_agent(
            model=chat_model,
            tools=[echo],
            system_prompt=self._settings.langgraph_system_prompt,
        )

    @staticmethod
    def _final_text(messages: list[Any]) -> str:
        for message in reversed(messages):
            if isinstance(message, AIMessage):
                content = message.content
                if isinstance(content, str):
                    return content
                if isinstance(content, list):
                    parts: list[str] = []
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text = block.get("text", "")
                            if isinstance(text, str):
                                parts.append(text)
                    return "".join(parts)
        return ""

    @staticmethod
    def _collect_tool_calls(messages: list[Any]) -> list[dict[str, Any]]:
        collected: list[dict[str, Any]] = []
        for message in messages:
            tc = getattr(message, "tool_calls", None)
            if not tc:
                continue
            for tool_call in tc:
                collected.append(
                    {
                        "name": tool_call.get("name"),
                        "args": tool_call.get("args"),
                    }
                )
        return collected
