from __future__ import annotations

from azure.identity import DefaultAzureCredential
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from concierge.chat.domain.entities import Conversation, Message
from concierge.chat.domain.value_objects import MessageRole


class FoundryChatbotResponder:
    def __init__(self, model: str, system_prompt: str) -> None:
        self._model = model
        self._system_prompt = system_prompt

    def generate_reply(self, conversation: Conversation, history: list[Message]) -> str:
        chat_model = init_chat_model(
            self._model,
            credential=DefaultAzureCredential(),
        )
        lc_messages: list[SystemMessage | HumanMessage | AIMessage] = [
            SystemMessage(content=self._system_prompt),
        ]
        # history is newest-first; reverse for chronological order
        for msg in reversed(history):
            if msg.role == MessageRole.USER:
                lc_messages.append(HumanMessage(content=msg.content))
            elif msg.role == MessageRole.AGENT:
                lc_messages.append(AIMessage(content=msg.content))
        response = chat_model.invoke(lc_messages)
        content = response.content
        return content if isinstance(content, str) else str(content)
