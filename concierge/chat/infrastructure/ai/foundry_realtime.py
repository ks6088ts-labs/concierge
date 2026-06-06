"""Foundry Realtime WebSocket client.

Connects to ``wss://<host>/openai/v1/realtime?model=<deployment>`` (GA URL
format) using the ``websockets`` library (sync client) and
``DefaultAzureCredential`` for auth.
"""

from __future__ import annotations

import json
import logging
import queue
import threading
from collections.abc import Iterator
from typing import Any, cast

import websockets.sync.client as ws_sync
from azure.identity import DefaultAzureCredential

from concierge.chat.application.realtime_tools import RealtimeTool
from concierge.chat.application.responders import RealtimeVoiceSession
from concierge.chat.domain.entities import Conversation, Message
from concierge.chat.domain.value_objects import MessageRole
from concierge.chat.infrastructure.ai.exceptions import ChatbotNotConfiguredError

logger = logging.getLogger(__name__)

# Cognitive Services scope used for all Azure OpenAI / Foundry calls
_COGNITIVE_SERVICES_SCOPE = "https://cognitiveservices.azure.com/.default"

_SENTINEL = object()  # signals end of iter_server_events


def _derive_wss_host(endpoint: str) -> str:
    """Derive the WSS host from ``AZURE_AI_PROJECT_ENDPOINT_REALTIME``.

    Raises:
        ChatbotNotConfiguredError: if the endpoint is empty, uses a non-https
            scheme, or cannot be parsed.
    """
    if not endpoint or not endpoint.strip():
        raise ChatbotNotConfiguredError(
            "AZURE_AI_PROJECT_ENDPOINT_REALTIME is not configured.",
        )

    stripped = endpoint.strip()

    # Must start with https://
    if not stripped.startswith("https://"):
        raise ChatbotNotConfiguredError(
            f"AZURE_AI_PROJECT_ENDPOINT_REALTIME must start with https://; got: {stripped!r}",
        )

    # Extract the host part (after "https://", before the first "/" if any)
    rest = stripped[len("https://") :]
    host = rest.split("/")[0]
    if not host:
        raise ChatbotNotConfiguredError(
            f"Cannot derive host from AZURE_AI_PROJECT_ENDPOINT_REALTIME: {stripped!r}",
        )

    # Normalise services.ai.azure.com → openai.azure.com
    if host.endswith(".services.ai.azure.com"):
        resource = host.split(".")[0]
        host = f"{resource}.openai.azure.com"

    return host


def build_turn_detection(
    detection_type: str,
    *,
    threshold: float = 0.5,
    prefix_padding_ms: int = 300,
    silence_duration_ms: int = 700,
    eagerness: str = "low",
    create_response: bool = True,
    interrupt_response: bool = True,
) -> dict[str, Any] | None:
    """Build the ``audio.input.turn_detection`` block for ``session.update``.

    Returns ``None`` for push-to-talk (``none``/``null``), which the caller
    should translate into omitting the key entirely so the model performs no
    automatic turn-taking.

    See the VAD reference:
    https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/realtime-audio#voice-activity-detection-vad-and-the-audio-buffer
    """
    normalized = (detection_type or "").strip().lower()
    if normalized in {"none", "null"}:
        return None
    if normalized == "semantic_vad":
        # ``eagerness=low`` widens the wait timeout so the model lets the user
        # finish before responding — the documented fix for premature replies.
        return {
            "type": "semantic_vad",
            "eagerness": eagerness,
            "create_response": create_response,
            "interrupt_response": interrupt_response,
        }
    # Default / explicit ``server_vad``: silence-based detection.
    return {
        "type": "server_vad",
        "threshold": threshold,
        "prefix_padding_ms": prefix_padding_ms,
        "silence_duration_ms": silence_duration_ms,
        "create_response": create_response,
        "interrupt_response": interrupt_response,
    }


class _FoundryRealtimeSession:
    """Wraps a ``websockets`` sync connection in the :class:`RealtimeVoiceSession` protocol."""

    def __init__(
        self,
        wss_url: str,
        extra_headers: dict[str, str],
        session_config: dict[str, Any],
        initial_items: list[dict[str, Any]] | None = None,
    ) -> None:
        self._wss_url = wss_url
        self._extra_headers = extra_headers
        self._session_config = session_config
        self._event_queue: queue.Queue[object] = queue.Queue()
        self._conn = ws_sync.connect(wss_url, additional_headers=extra_headers)
        self._thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._thread.start()
        # Send the initial session.update event
        self.send_client_event({"type": "session.update", "session": session_config})
        # Seed history as separate conversation.item.create events
        for item in initial_items or []:
            self.send_client_event({"type": "conversation.item.create", "item": item})

    # ------------------------------------------------------------------
    # RealtimeVoiceSession protocol
    # ------------------------------------------------------------------

    def send_client_event(self, event: dict[str, Any]) -> None:
        self._conn.send(json.dumps(event))

    def iter_server_events(self) -> Iterator[dict[str, Any]]:
        while True:
            item = self._event_queue.get()
            if item is _SENTINEL:
                return
            yield cast("dict[str, Any]", item)

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:  # noqa: BLE001
            pass
        self._thread.join(timeout=5)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _recv_loop(self) -> None:
        try:
            for raw in self._conn:
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    logger.warning("Received non-JSON frame from Foundry, skipping")
                    continue
                # Log key lifecycle / VAD / transcription events at INFO so we
                # can diagnose "voice not recognized" issues without enabling
                # DEBUG (which would dump every audio delta).
                ev_type = event.get("type", "")
                if ev_type in {
                    "session.created",
                    "session.updated",
                    "error",
                    "input_audio_buffer.speech_started",
                    "input_audio_buffer.speech_stopped",
                    "input_audio_buffer.committed",
                    "input_audio_buffer.cleared",
                    "conversation.item.input_audio_transcription.completed",
                    "conversation.item.input_audio_transcription.failed",
                    "response.output_audio_transcript.done",
                    "response.done",
                }:
                    logger.info("Foundry event: %s", ev_type)
                self._event_queue.put(event)
        except Exception:  # noqa: BLE001
            logger.exception("Foundry WS receive loop terminated")
        finally:
            self._event_queue.put(_SENTINEL)


class FoundryRealtimeResponder:
    """Opens a Foundry ``/openai/v1/realtime`` WebSocket session.

    This path does not use LangChain today, so ``trace_config()`` integration is
    intentionally out of scope. If this responder is migrated to LangChain in
    the future, adopt ``concierge.observability.trace_config("concierge-chat")``.
    """

    def __init__(
        self,
        endpoint_realtime: str,
        deployment: str,
        voice: str,
        locale: str,
        system_prompt: str,
        transcription_model: str = "",
        tools: list[RealtimeTool] | None = None,
        *,
        turn_detection_type: str = "server_vad",
        vad_threshold: float = 0.5,
        vad_prefix_padding_ms: int = 300,
        vad_silence_duration_ms: int = 700,
        vad_eagerness: str = "low",
        vad_create_response: bool = True,
        vad_interrupt_response: bool = True,
    ) -> None:
        self._host = _derive_wss_host(endpoint_realtime)
        self._deployment = deployment
        self._voice = voice
        self._locale = locale
        self._system_prompt = system_prompt
        self._transcription_model = transcription_model
        self._tools = tools or []
        self._turn_detection = build_turn_detection(
            turn_detection_type,
            threshold=vad_threshold,
            prefix_padding_ms=vad_prefix_padding_ms,
            silence_duration_ms=vad_silence_duration_ms,
            eagerness=vad_eagerness,
            create_response=vad_create_response,
            interrupt_response=vad_interrupt_response,
        )

    def open(self, conversation: Conversation, history: list[Message]) -> RealtimeVoiceSession:
        token = DefaultAzureCredential().get_token(_COGNITIVE_SERVICES_SCOPE).token
        # GA URL format: /openai/v1/realtime?model=<deployment>
        # (preview format would be /openai/realtime?api-version=...&deployment=<deployment>;
        # mixing the two causes HTTP 400/404 at the WebSocket handshake.)
        # See: https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/realtime-audio-websockets
        wss_url = f"wss://{self._host}/openai/v1/realtime?model={self._deployment}"
        headers = {
            "Authorization": f"Bearer {token}",
        }
        # Foundry GA endpoint (``/openai/v1/realtime``) requires ``session.type``
        # and uses a nested ``audio.input`` / ``audio.output`` schema. The flat
        # ``voice`` / ``input_audio_format`` / ``turn_detection`` keys accepted
        # by the preview API are rejected with ``invalid_request_error /
        # unknown_parameter`` on GA.
        input_audio: dict[str, Any] = {
            "format": {"type": "audio/pcm", "rate": 24000},
        }
        # ``turn_detection`` controls how eagerly the model takes its turn. When
        # ``None`` (push-to-talk), omit the key so the model performs no
        # automatic turn-taking and waits for client-driven commits.
        if self._turn_detection is not None:
            input_audio["turn_detection"] = self._turn_detection
        if self._transcription_model:
            # On Azure the ``model`` field must be a deployment name in the same
            # resource. Omit the block entirely when no deployment is configured
            # — Foundry will then skip user-side transcription instead of
            # silently failing.
            input_audio["transcription"] = {
                "model": self._transcription_model,
                # Foundry GA accepts ISO 639-1 (``ja``), not BCP-47 (``ja-JP``).
                # Strip the region subtag so ``.env`` can keep using either form.
                "language": self._locale.replace("_", "-").split("-", 1)[0].lower(),
            }
        session_config: dict[str, Any] = {
            "type": "realtime",
            "instructions": self._system_prompt,
            "audio": {
                "input": input_audio,
                "output": {
                    "format": {"type": "audio/pcm", "rate": 24000},
                    "voice": self._voice,
                },
            },
        }
        # Advertise function tools so the model can request tool calls. The relay
        # (StreamRealtimeVoiceUseCase) executes them and returns the result.
        if self._tools:
            session_config["tools"] = [tool.to_session_tool() for tool in self._tools]
            session_config["tool_choice"] = "auto"
        # Build initial conversation items from history (newest-first → reverse for
        # chronological order). These must be sent as separate ``conversation.item.create``
        # events *after* the ``session.update`` event — they are not valid fields inside
        # ``session.update`` itself.
        initial_items: list[dict[str, Any]] = []
        for msg in reversed(history):
            if msg.role == MessageRole.USER:
                initial_items.append(
                    {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": msg.content}],
                    }
                )
            elif msg.role == MessageRole.AGENT:
                initial_items.append(
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "text", "text": msg.content}],
                    }
                )

        return _FoundryRealtimeSession(wss_url, headers, session_config, initial_items)
