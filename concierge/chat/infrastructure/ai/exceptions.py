"""Exceptions for the AI infrastructure layer."""

from __future__ import annotations


class ChatbotNotConfiguredError(RuntimeError):
    """Raised when the chatbot or realtime responder dependencies are missing."""
