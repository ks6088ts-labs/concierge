from __future__ import annotations

import uuid


class ConversationNotFoundError(Exception):
    """Raised when a conversation is not found."""

    def __init__(self, conversation_id: uuid.UUID):
        self.conversation_id = conversation_id
        super().__init__(f"Conversation not found: {conversation_id}")


class MessageValidationError(Exception):
    """Raised when message validation fails."""

    def __init__(self, message: str):
        super().__init__(message)


class ParticipantValidationError(Exception):
    """Raised when participant validation fails."""

    def __init__(self, message: str):
        super().__init__(message)
