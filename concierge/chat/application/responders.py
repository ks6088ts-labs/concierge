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
    """

    def stream_reply(
        self,
        conversation: Conversation,
        history: list[Message],
    ) -> Iterator[str]: ...
