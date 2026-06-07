from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from concierge.chat.domain.entities import Conversation, Message


class ChatbotResponder(Protocol):
    """Generates AI replies as a stream of text deltas.

    Implementations must yield non-empty string chunks in chronological order.
    The use case concatenates the chunks to form the final persisted message
    content. Streaming is required so that the transport layer can deliver
    incremental updates to clients (e.g. Server-Sent Events).

    ``image_url`` is an optional inline ``data:image/*;base64,…`` URL captured by
    the client for the current turn. It is request-scoped and ephemeral (never
    persisted). Vision-capable implementations ground the reply in the image;
    text-only implementations may ignore it.
    """

    def stream_reply(
        self,
        conversation: Conversation,
        history: list[Message],
        image_url: str | None = None,
    ) -> Iterator[str]: ...


class RealtimeVoiceSession(Protocol):
    """A single open realtime session against the upstream model."""

    def send_client_event(self, event: dict) -> None: ...  # type: ignore[type-arg]

    def iter_server_events(self) -> Iterator[dict]: ...  # type: ignore[type-arg]

    def close(self) -> None: ...


class RealtimeVoiceResponder(Protocol):
    """Bidirectional streaming responder for realtime voice conversations."""

    def open(
        self,
        conversation: Conversation,
        history: list[Message],
    ) -> RealtimeVoiceSession: ...
