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

This module deliberately stays free of framework/IO dependencies so it can live
in the application layer. The LangChain adapter that bridges reusable tools from
``concierge.agents.infrastructure.tools`` into :class:`RealtimeTool` instances
lives in ``concierge.chat.infrastructure.ai.realtime_tools`` instead.
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
# Camera capture (accessibility / hands-free image input)
# ---------------------------------------------------------------------------

# Name of the tool the model calls to take a photo with the user's camera. The
# actual capture happens in the browser, so :class:`StreamRealtimeVoiceUseCase`
# special-cases this tool (asking the client to capture) instead of running the
# placeholder handler below. Kept as a shared constant so the use case and the
# tool definition agree on the name.
CAPTURE_IMAGE_TOOL_NAME = "capture_image"


def _capture_image_placeholder(arguments: dict[str, Any]) -> str:
    """Fallback handler for ``capture_image``.

    Never invoked in practice: the use case intercepts ``capture_image`` before
    the generic tool-handler path and asks the browser to take the photo. This
    exists only to satisfy the :class:`RealtimeTool` contract.
    """
    return json.dumps({"status": "capturing"})


def build_capture_image_tool() -> RealtimeTool:
    """Build the ``capture_image`` realtime tool (voice-triggered camera).

    Exposed only to the accessibility mode session so a blind user can take a
    photo hands-free by asking for it. When the model calls this tool the use
    case asks the browser to capture a frame; the captured image is injected
    back into the conversation and the model then describes it.
    """
    return RealtimeTool(
        name=CAPTURE_IMAGE_TOOL_NAME,
        description=(
            "Take a photo with the user's camera and analyze it. Use this "
            "whenever the user asks you to take a picture, look at something, "
            "or describe what is in front of them (e.g. '写真を撮って', "
            "'これ何が見える?', 'カメラで見て', '周りを教えて'). After the image "
            "is captured, describe what you see clearly and concretely."
        ),
        parameters={
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": (
                        "Optional focus for the description, e.g. 'read the "
                        "text', 'what color is this', 'is it safe to cross'."
                    ),
                },
            },
            "required": [],
        },
        handler=_capture_image_placeholder,
    )
