"""Tool (function-calling) support for realtime voice sessions.

The Foundry GA realtime endpoint (``/openai/v1/realtime``) follows the OpenAI
Realtime API contract for function calling:

1. ``session.update`` advertises the available tools under ``session.tools``.
2. When the model decides to call a tool it emits a ``function_call`` item,
   surfaced to us as a ``response.output_item.done`` server event.
3. We run the tool locally and reply with a ``conversation.item.create`` event
   carrying a ``function_call_output`` item, then trigger ``response.create`` so
   the model can continue speaking with the result in context.

This module keeps the tool *contract* (schema) and *implementation* (handler)
together in a single :class:`RealtimeTool` so the responder (which needs the
schema) and the use case (which needs the handler) can share one source of
truth.

Rather than hand-writing each tool here, :func:`realtime_tool_from_langchain`
adapts the reusable LangChain tool *builders* defined under
``concierge.agents.infrastructure.tools`` (echo, file management, shell,
image generation, knowledge, ...) into :class:`RealtimeTool` instances. This
lets the realtime agent share the exact same tool implementations as the
text/agent surfaces instead of maintaining a parallel, ad-hoc copy.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# A handler receives the parsed JSON arguments and returns a string that is sent
# back to the model verbatim as the ``function_call_output``. Returning JSON is
# recommended but plain text is also accepted by the model.
ToolHandler = Callable[[dict[str, Any]], str]

# A LangChain tool *builder*: called with a fresh ``side_outputs`` dict per
# invocation and returns a LangChain ``BaseTool``. This matches the contract
# used by the agent classes under ``concierge.agents.infrastructure.tools``.
ToolBuilder = Callable[[dict[str, Any]], Any]


@dataclass(frozen=True)
class RealtimeTool:
    """A single function tool exposed to the realtime model."""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler

    def to_session_tool(self) -> dict[str, Any]:
        """Render the schema advertised in ``session.update`` → ``session.tools``."""
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


# ---------------------------------------------------------------------------
# Native tools (no framework dependency)
# ---------------------------------------------------------------------------


def _get_current_time(arguments: dict[str, Any]) -> str:
    """Return the current date/time, optionally in a given IANA timezone."""
    tz_name = arguments.get("timezone") or "UTC"
    try:
        tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        return json.dumps({"error": f"unknown timezone: {tz_name!r}"})
    now = datetime.now(tz)
    return json.dumps(
        {
            "timezone": tz_name,
            "iso8601": now.isoformat(),
            "human_readable": now.strftime("%Y-%m-%d %H:%M:%S %Z"),
        }
    )


def build_get_current_time_tool() -> RealtimeTool:
    """Build the native ``get_current_time`` realtime tool."""
    return RealtimeTool(
        name="get_current_time",
        description=(
            "Get the current date and time. Use this whenever the user asks "
            "what time or date it is. Optionally accepts an IANA timezone "
            "name such as 'Asia/Tokyo'."
        ),
        parameters={
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": "IANA timezone name, e.g. 'Asia/Tokyo'. Defaults to UTC.",
                },
            },
            "required": [],
        },
        handler=_get_current_time,
    )


# ---------------------------------------------------------------------------
# Generic LangChain tool adapter
# ---------------------------------------------------------------------------


def _run_coroutine(coro: Any) -> Any:
    """Run an awaitable to completion from a synchronous context.

    The realtime relay runs in a background thread without an event loop, so
    ``asyncio.run`` works directly. If a loop is already running (e.g. when
    called from async code) we fall back to a short-lived worker thread.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def _invoke_langchain_tool(lc_tool: Any, arguments: dict[str, Any]) -> Any:
    """Invoke a LangChain tool, transparently supporting async-only tools."""
    try:
        return lc_tool.invoke(arguments)
    except NotImplementedError:
        # Tools defined with ``async def`` have no sync implementation.
        return _run_coroutine(lc_tool.ainvoke(arguments))


def _to_output_string(result: Any) -> str:
    """Coerce a tool result into the string sent back as ``function_call_output``."""
    if isinstance(result, str):
        return result
    try:
        return json.dumps(result, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(result)


def realtime_tool_from_langchain(lc_tool: Any) -> RealtimeTool:
    """Adapt a LangChain ``BaseTool`` into a :class:`RealtimeTool`.

    The JSON schema advertised to the model is derived from the tool's
    ``args_schema`` via LangChain's OpenAI conversion helper, and the handler
    invokes the same tool implementation used by the agent surfaces.
    """
    from langchain_core.utils.function_calling import convert_to_openai_tool

    function_schema = convert_to_openai_tool(lc_tool)["function"]
    parameters = function_schema.get("parameters") or {"type": "object", "properties": {}}

    def _handler(arguments: dict[str, Any]) -> str:
        return _to_output_string(_invoke_langchain_tool(lc_tool, arguments))

    return RealtimeTool(
        name=function_schema["name"],
        description=function_schema.get("description", ""),
        parameters=parameters,
        handler=_handler,
    )


def realtime_tools_from_builders(
    builders: Iterable[ToolBuilder],
    side_outputs: dict[str, Any] | None = None,
) -> list[RealtimeTool]:
    """Build LangChain tools from ``builders`` and adapt them to realtime tools.

    Each builder is called with a shared ``side_outputs`` dict (matching the
    agent-class contract) so tools that emit side outputs keep working. Side
    outputs are not surfaced to the realtime model, but the dict must be passed
    to satisfy the builder signature.
    """
    outputs = side_outputs if side_outputs is not None else {}
    return [realtime_tool_from_langchain(build(outputs)) for build in builders]


# ---------------------------------------------------------------------------
# Default tool set
# ---------------------------------------------------------------------------


def build_default_realtime_tools(
    *,
    file_root_dir: str = "",
    enabled_file_tools: Sequence[str] | None = None,
) -> list[RealtimeTool]:
    """Build the default tool set advertised to the realtime model.

    The default set combines the native ``get_current_time`` tool with reusable
    LangChain tools from ``concierge.agents.infrastructure.tools``: the ``echo``
    tool and read-only file-management tools (``read_file``, ``list_directory``,
    ``file_search``) sandboxed under ``file_root_dir`` (defaults to the
    ``workspace`` directory).

    To grow the agent's capabilities, append additional LangChain tool builders
    via :func:`realtime_tools_from_builders`, or hand-write a
    :class:`RealtimeTool` for native (non-LangChain) behavior.
    """
    from concierge.agents.infrastructure.tools import (
        READ_ONLY_FILE_TOOLS,
        build_echo_langchain_tool,
        build_file_langchain_tool_builders,
    )

    file_tools = enabled_file_tools if enabled_file_tools is not None else READ_ONLY_FILE_TOOLS
    builders: list[ToolBuilder] = [
        build_echo_langchain_tool,
        *build_file_langchain_tool_builders(file_root_dir, file_tools),
    ]

    return [
        build_get_current_time_tool(),
        *realtime_tools_from_builders(builders),
    ]
