from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from azure.identity import DefaultAzureCredential
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from concierge.chat.domain.entities import Conversation, Message
from concierge.chat.domain.value_objects import MessageRole


def _extract_text(content: Any) -> str:
    """Extract plain text from a LangChain message chunk's ``content``.

    ``content`` may be either a ``str`` (classic chat completions) or a
    ``list`` of content blocks (e.g. Foundry / Responses API which interleaves
    ``reasoning`` blocks and ``text`` blocks). Only blocks whose ``type`` is
    ``"text"`` contribute to the rendered message body. Other block types such
    as ``"reasoning"`` are intentionally ignored so they don't pollute the
    persisted message content.
    """

    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
            continue
        if isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text", "")
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts)


class FoundryChatbotResponder:
    def __init__(self, model: str, system_prompt: str) -> None:
        self._model = model
        self._system_prompt = system_prompt

    def stream_reply(self, conversation: Conversation, history: list[Message]) -> Iterator[str]:
        # ``langchain_azure_ai`` resolves ``project_endpoint`` from the
        # ``AZURE_AI_PROJECT_ENDPOINT`` / ``FOUNDRY_PROJECT_ENDPOINT`` environment
        # variables. The web and CLI entry points call ``load_dotenv()`` so that
        # ``.env`` values are present in ``os.environ`` for these libraries that
        # read environment variables directly (pydantic-settings reads ``.env``
        # but does not export to ``os.environ``).
        chat_model = init_chat_model(self._model, credential=DefaultAzureCredential())
        lc_messages: list[SystemMessage | HumanMessage | AIMessage] = [
            SystemMessage(content=self._system_prompt),
        ]
        # history is newest-first; reverse for chronological order
        for msg in reversed(history):
            if msg.role == MessageRole.USER:
                lc_messages.append(HumanMessage(content=msg.content))
            elif msg.role == MessageRole.AGENT:
                lc_messages.append(AIMessage(content=msg.content))
        for chunk in chat_model.stream(lc_messages):
            text = _extract_text(chunk.content)
            if text:
                yield text
