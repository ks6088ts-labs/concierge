"""LangChain adapter that bridges reusable agent tools into realtime tools.

The pure :class:`~concierge.chat.application.realtime_tools.RealtimeTool`
contract lives in the application layer. This infrastructure module adapts the
reusable LangChain tool *builders* defined under
``concierge.agents.infrastructure.tools`` (echo, file management, shell,
image generation, knowledge, ...) into :class:`RealtimeTool` instances so the
realtime agent shares the exact same tool implementations as the text/agent
surfaces instead of maintaining a parallel, ad-hoc copy.

Keeping the framework (LangChain) and persistence/IO dependencies here preserves
the clean-architecture rule that the application layer stays free of web,
persistence, and framework imports.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from concierge.chat.application.realtime_tools import (
    RealtimeTool,
    build_get_current_time_tool,
)

# A LangChain tool *builder*: called with a fresh ``side_outputs`` dict per
# invocation and returns a LangChain ``BaseTool``. This matches the contract
# used by the agent classes under ``concierge.agents.infrastructure.tools``.
ToolBuilder = Callable[[dict[str, Any]], Any]


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


def build_default_realtime_tools(
    *,
    file_root_dir: str = "",
    enabled_file_tools: Sequence[str] | None = None,
) -> list[RealtimeTool]:
    """Build the default tool set advertised to the realtime model.

    The default set combines the native ``get_current_time`` tool with reusable
    LangChain tools from ``concierge.agents.infrastructure.tools``: the ``echo``
    tool, read-only file-management tools (``read_file``, ``list_directory``,
    ``file_search``) sandboxed under ``file_root_dir`` (defaults to the
    ``workspace`` directory), and optional knowledge-retrieval tools configured
    via ``AGENTS_KNOWLEDGE__...`` settings.

    To grow the agent's capabilities, append additional LangChain tool builders
    via :func:`realtime_tools_from_builders`, or hand-write a
    :class:`RealtimeTool` for native (non-LangChain) behavior.
    """
    from concierge.agents.infrastructure.tools import (
        READ_ONLY_FILE_TOOLS,
        build_echo_langchain_tool,
        build_file_langchain_tool_builders,
        build_knowledge_langchain_tool_builders,
    )
    from concierge.settings.agents_knowledge import get_agents_knowledge_settings

    file_tools = enabled_file_tools if enabled_file_tools is not None else READ_ONLY_FILE_TOOLS
    builders: list[ToolBuilder] = [
        build_echo_langchain_tool,
        *build_file_langchain_tool_builders(file_root_dir, file_tools),
        *build_knowledge_langchain_tool_builders(get_agents_knowledge_settings()),
    ]

    return [
        build_get_current_time_tool(),
        *realtime_tools_from_builders(builders),
    ]
