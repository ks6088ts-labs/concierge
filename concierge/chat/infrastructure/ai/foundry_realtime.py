"""Foundry Realtime WebSocket client.

Connects to ``wss://<host>/openai/v1/realtime?model=<deployment>`` using the
``websockets`` library (sync client) and ``DefaultAzureCredential`` for auth.
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


class _FoundryRealtimeSession:
    """Wraps a ``websockets`` sync connection in the :class:`RealtimeVoiceSession` protocol."""

    def __init__(
        self,
        wss_url: str,
        extra_headers: dict[str, str],
        session_config: dict[str, Any],
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
                self._event_queue.put(event)
        except Exception:  # noqa: BLE001
            logger.exception("Foundry WS receive loop terminated")
        finally:
            self._event_queue.put(_SENTINEL)


class FoundryRealtimeResponder:
    """Opens a Foundry ``/openai/v1/realtime`` WebSocket session."""

    def __init__(
        self,
        endpoint_realtime: str,
        deployment: str,
        voice: str,
        locale: str,
        system_prompt: str,
    ) -> None:
        self._host = _derive_wss_host(endpoint_realtime)
        self._deployment = deployment
        self._voice = voice
        self._locale = locale
        self._system_prompt = system_prompt

    def open(self, conversation: Conversation, history: list[Message]) -> RealtimeVoiceSession:
        token = DefaultAzureCredential().get_token(_COGNITIVE_SERVICES_SCOPE).token
        wss_url = f"wss://{self._host}/openai/realtime?model={self._deployment}&api-version=2025-04-01-preview"
        headers = {
            "Authorization": f"Bearer {token}",
            "OpenAI-Beta": "realtime=v1",
        }
        session_config: dict[str, Any] = {
            "voice": self._voice,
            "instructions": self._system_prompt,
            "input_audio_format": "pcm16",
            "output_audio_format": "pcm16",
            "turn_detection": {"type": "server_vad"},
            "input_audio_transcription": {
                "model": "gpt-4o-mini-transcribe",
                "language": self._locale,
            },
        }
        # Build initial context from history as a list of conversation items
        # (newest-first → reverse for chronological order)
        input_items = []
        for msg in reversed(history):
            if msg.role == MessageRole.USER:
                input_items.append(
                    {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": msg.content}],
                    }
                )
            elif msg.role == MessageRole.AGENT:
                input_items.append(
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "text", "text": msg.content}],
                    }
                )
        if input_items:
            session_config["input"] = input_items

        return _FoundryRealtimeSession(wss_url, headers, session_config)
