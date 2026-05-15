from __future__ import annotations

import logging
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime

from concierge.chat.application.repositories import ConversationRepository, MessageRepository
from concierge.chat.application.responders import ChatbotResponder
from concierge.chat.domain.entities import Conversation, Message
from concierge.chat.domain.exceptions import ConversationNotFoundError, MessageValidationError
from concierge.chat.domain.value_objects import MessageRole, Participant

logger = logging.getLogger(__name__)


class CreateConversationUseCase:
    def __init__(self, conversation_repository: ConversationRepository):
        self.conversation_repository = conversation_repository

    def execute(self, title: str, creator: Participant) -> Conversation:
        conversation = Conversation(title=title, participants=[creator])
        created = self.conversation_repository.save(conversation)
        logger.info("Created conversation id=%s", created.id)
        return created


class GetConversationUseCase:
    def __init__(self, conversation_repository: ConversationRepository):
        self.conversation_repository = conversation_repository

    def execute(self, conversation_id: uuid.UUID) -> Conversation:
        conversation = self.conversation_repository.find_by_id(conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(conversation_id)
        return conversation


class ListConversationsUseCase:
    def __init__(self, conversation_repository: ConversationRepository):
        self.conversation_repository = conversation_repository

    def execute(self, participant_id: uuid.UUID | None = None) -> list[Conversation]:
        return self.conversation_repository.find_all(participant_id=participant_id)


class JoinConversationUseCase:
    def __init__(self, conversation_repository: ConversationRepository):
        self.conversation_repository = conversation_repository

    def execute(self, conversation_id: uuid.UUID, participant: Participant) -> Conversation:
        conversation = self.conversation_repository.find_by_id(conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(conversation_id)
        conversation.add_participant(participant)
        updated = self.conversation_repository.save(conversation)
        logger.info("Joined conversation id=%s participant=%s", updated.id, participant.id)
        return updated


class PostMessageUseCase:
    def __init__(self, conversation_repository: ConversationRepository, message_repository: MessageRepository):
        self.conversation_repository = conversation_repository
        self.message_repository = message_repository

    def execute(self, conversation_id: uuid.UUID, sender: Participant, content: str) -> Message:
        conversation = self.conversation_repository.find_by_id(conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(conversation_id)
        if all(participant.id != sender.id for participant in conversation.participants):
            raise MessageValidationError("sender is not a participant in this conversation")
        message = Message(conversation_id=conversation_id, sender=sender, content=content)
        created = self.message_repository.save(message)
        logger.info("Posted message id=%s", created.id)
        return created


class ListMessagesUseCase:
    def __init__(self, conversation_repository: ConversationRepository, message_repository: MessageRepository):
        self.conversation_repository = conversation_repository
        self.message_repository = message_repository

    def execute(
        self,
        conversation_id: uuid.UUID,
        *,
        limit: int = 100,
        before: datetime | None = None,
    ) -> list[Message]:
        if self.conversation_repository.find_by_id(conversation_id) is None:
            raise ConversationNotFoundError(conversation_id)
        return self.message_repository.find_by_conversation(conversation_id, limit=limit, before=before)


class DeleteConversationUseCase:
    def __init__(self, conversation_repository: ConversationRepository, message_repository: MessageRepository):
        self.conversation_repository = conversation_repository
        self.message_repository = message_repository

    def execute(self, conversation_id: uuid.UUID) -> None:
        if self.conversation_repository.find_by_id(conversation_id) is None:
            raise ConversationNotFoundError(conversation_id)
        deleted_messages = self.message_repository.delete_by_conversation(conversation_id)
        self.conversation_repository.delete(conversation_id)
        logger.info("Deleted conversation id=%s messages=%s", conversation_id, deleted_messages)


class GenerateBotReplyUseCase:
    """Stream an AI bot reply for a conversation.

    ``execute()`` performs synchronous validation (conversation existence) and
    returns an iterator that yields :class:`BotReplyEvent` values. Validation
    errors propagate before the iterator starts so that transport layers can
    map them to HTTP errors via the regular exception handlers.
    """

    def __init__(
        self,
        conversation_repository: ConversationRepository,
        message_repository: MessageRepository,
        responder: ChatbotResponder,
        bot_participant: Participant,
        history_limit: int = 20,
    ):
        self.conversation_repository = conversation_repository
        self.message_repository = message_repository
        self.responder = responder
        self.bot_participant = bot_participant
        self.history_limit = history_limit

    def execute(self, conversation_id: uuid.UUID) -> Iterator[BotReplyEvent]:
        conversation = self.conversation_repository.find_by_id(conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(conversation_id)
        history = self.message_repository.find_by_conversation(conversation_id, limit=self.history_limit)
        conversation.add_participant(self.bot_participant)
        self.conversation_repository.save(conversation)
        return self._stream(conversation, history, conversation_id)

    def _stream(
        self,
        conversation: Conversation,
        history: list[Message],
        conversation_id: uuid.UUID,
    ) -> Iterator[BotReplyEvent]:
        chunks: list[str] = []
        for chunk in self.responder.stream_reply(conversation, history):
            if not chunk:
                continue
            chunks.append(chunk)
            yield BotReplyDelta(content=chunk)
        message = Message(
            conversation_id=conversation_id,
            sender=self.bot_participant,
            content="".join(chunks),
            role=MessageRole.AGENT,
        )
        saved = self.message_repository.save(message)
        logger.info("Bot replied message id=%s in conversation=%s", saved.id, conversation_id)
        yield BotReplyComplete(message=saved)


@dataclass(frozen=True)
class BotReplyDelta:
    """Incremental text chunk emitted while the bot is generating."""

    content: str


@dataclass(frozen=True)
class BotReplyComplete:
    """Terminal event carrying the persisted :class:`Message`."""

    message: Message


BotReplyEvent = BotReplyDelta | BotReplyComplete
