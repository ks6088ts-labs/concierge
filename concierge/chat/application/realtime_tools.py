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
truth via :func:`build_default_realtime_tools`.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# A handler receives the parsed JSON arguments and returns a string that is sent
# back to the model verbatim as the ``function_call_output``. Returning JSON is
# recommended but plain text is also accepted by the model.
ToolHandler = Callable[[dict[str, Any]], str]


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


def build_default_realtime_tools() -> list[RealtimeTool]:
    """Build the default tool set advertised to the realtime model.

    Add new :class:`RealtimeTool` entries here to grow the agent's capabilities.
    Each tool must be pure-Python and reasonably fast: the realtime relay runs it
    synchronously between audio turns.
    """
    return [
        RealtimeTool(
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
        ),
    ]
