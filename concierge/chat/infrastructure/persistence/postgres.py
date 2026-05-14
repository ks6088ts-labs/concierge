from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import text

from concierge.chat.domain.entities import Conversation, Message
from concierge.chat.domain.value_objects import MessageRole, Participant, ParticipantKind

if TYPE_CHECKING:
    from sqlalchemy import Engine

_VALID_TABLE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_table_name(table_name: str) -> str:
    if not _VALID_TABLE_NAME.fullmatch(table_name):
        raise ValueError(f"Invalid SQL table name: {table_name!r}")
    return table_name


class SqlAlchemyConversationRepository:
    def __init__(self, engine: Engine, conversations_table_name: str, participants_table_name: str):
        self._engine = engine
        self._conversations_table_name = _validate_table_name(conversations_table_name)
        self._participants_table_name = _validate_table_name(participants_table_name)

    def init_schema(self) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self._conversations_table_name} (
                        id          UUID PRIMARY KEY,
                        title       VARCHAR(200)  NOT NULL,
                        created_at  TIMESTAMPTZ   NOT NULL,
                        updated_at  TIMESTAMPTZ   NOT NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self._participants_table_name} (
                        conversation_id UUID NOT NULL REFERENCES {self._conversations_table_name}(id) ON DELETE CASCADE,
                        participant_id  UUID NOT NULL,
                        kind            VARCHAR(16) NOT NULL,
                        display_name    VARCHAR(100) NOT NULL,
                        PRIMARY KEY (conversation_id, participant_id)
                    )
                    """
                )
            )
            conn.execute(
                text(
                    f"CREATE INDEX IF NOT EXISTS idx_{self._participants_table_name}_pid "
                    f"ON {self._participants_table_name} (participant_id)"
                )
            )

    def drop_schema(self) -> None:
        with self._engine.begin() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS {self._participants_table_name}"))
            conn.execute(text(f"DROP TABLE IF EXISTS {self._conversations_table_name}"))

    def ping(self) -> None:
        with self._engine.connect() as conn:
            conn.execute(text("SELECT 1"))

    def save(self, conversation: Conversation) -> Conversation:
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    f"""
                    INSERT INTO {self._conversations_table_name}
                        (id, title, created_at, updated_at)
                    VALUES
                        (:id, :title, :created_at, :updated_at)
                    ON CONFLICT (id) DO UPDATE SET
                        title = EXCLUDED.title,
                        updated_at = EXCLUDED.updated_at
                    """
                ),
                {
                    "id": str(conversation.id),
                    "title": conversation.title,
                    "created_at": conversation.created_at,
                    "updated_at": conversation.updated_at,
                },
            )
            conn.execute(
                text(f"DELETE FROM {self._participants_table_name} WHERE conversation_id = :conversation_id"),
                {"conversation_id": str(conversation.id)},
            )
            for participant in conversation.participants:
                conn.execute(
                    text(
                        f"""
                        INSERT INTO {self._participants_table_name}
                            (conversation_id, participant_id, kind, display_name)
                        VALUES
                            (:conversation_id, :participant_id, :kind, :display_name)
                        """
                    ),
                    {
                        "conversation_id": str(conversation.id),
                        "participant_id": str(participant.id),
                        "kind": participant.kind.value,
                        "display_name": participant.display_name,
                    },
                )
        return conversation

    def find_by_id(self, conversation_id: uuid.UUID) -> Conversation | None:
        with self._engine.connect() as conn:
            conversation_row = conn.execute(
                text(f"SELECT * FROM {self._conversations_table_name} WHERE id = :id"),
                {"id": str(conversation_id)},
            ).fetchone()
            if conversation_row is None:
                return None
            participants_rows = conn.execute(
                text(
                    f"""
                    SELECT participant_id, kind, display_name
                    FROM {self._participants_table_name}
                    WHERE conversation_id = :conversation_id
                    ORDER BY display_name ASC
                    """
                ),
                {"conversation_id": str(conversation_id)},
            ).fetchall()
        return Conversation(
            id=_parse_uuid(conversation_row.id),
            title=conversation_row.title,
            participants=[
                Participant(
                    id=_parse_uuid(row.participant_id),
                    kind=ParticipantKind(row.kind),
                    display_name=row.display_name,
                )
                for row in participants_rows
            ],
            created_at=_ensure_datetime(conversation_row.created_at),
            updated_at=_ensure_datetime(conversation_row.updated_at),
        )

    def find_all(self, *, participant_id: uuid.UUID | None = None) -> list[Conversation]:
        with self._engine.connect() as conn:
            if participant_id is None:
                rows = conn.execute(
                    text(f"SELECT * FROM {self._conversations_table_name} ORDER BY created_at DESC")
                ).fetchall()
            else:
                rows = conn.execute(
                    text(
                        f"""
                        SELECT c.*
                        FROM {self._conversations_table_name} c
                        INNER JOIN {self._participants_table_name} p ON c.id = p.conversation_id
                        WHERE p.participant_id = :participant_id
                        ORDER BY c.created_at DESC
                        """
                    ),
                    {"participant_id": str(participant_id)},
                ).fetchall()
        return [conversation for row in rows if (conversation := self.find_by_id(_parse_uuid(row.id))) is not None]

    def delete(self, conversation_id: uuid.UUID) -> bool:
        with self._engine.begin() as conn:
            deleted_participants = conn.execute(
                text(f"DELETE FROM {self._participants_table_name} WHERE conversation_id = :conversation_id"),
                {"conversation_id": str(conversation_id)},
            )
            deleted_conversations = conn.execute(
                text(f"DELETE FROM {self._conversations_table_name} WHERE id = :id"),
                {"id": str(conversation_id)},
            )
        return deleted_conversations.rowcount > 0 or deleted_participants.rowcount > 0


class SqlAlchemyMessageRepository:
    def __init__(self, engine: Engine, messages_table_name: str, conversations_table_name: str):
        self._engine = engine
        self._messages_table_name = _validate_table_name(messages_table_name)
        self._conversations_table_name = _validate_table_name(conversations_table_name)

    def init_schema(self) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self._messages_table_name} (
                        id                  UUID PRIMARY KEY,
                        conversation_id     UUID NOT NULL
                                            REFERENCES {self._conversations_table_name}(id) ON DELETE CASCADE,
                        sender_id           UUID NOT NULL,
                        sender_kind         VARCHAR(16) NOT NULL,
                        sender_display_name VARCHAR(100) NOT NULL,
                        role                VARCHAR(16) NOT NULL,
                        content             VARCHAR(4000) NOT NULL,
                        created_at          TIMESTAMPTZ NOT NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    f"CREATE INDEX IF NOT EXISTS idx_{self._messages_table_name}_conv_created "
                    f"ON {self._messages_table_name} (conversation_id, created_at DESC)"
                )
            )

    def drop_schema(self) -> None:
        with self._engine.begin() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS {self._messages_table_name}"))

    def ping(self) -> None:
        with self._engine.connect() as conn:
            conn.execute(text("SELECT 1"))

    def save(self, message: Message) -> Message:
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    f"""
                    INSERT INTO {self._messages_table_name}
                        (id, conversation_id, sender_id, sender_kind, sender_display_name, role, content, created_at)
                    VALUES
                        (:id, :conversation_id, :sender_id, :sender_kind, :sender_display_name,
                         :role, :content, :created_at)
                    ON CONFLICT (id) DO UPDATE SET
                        sender_id = EXCLUDED.sender_id,
                        sender_kind = EXCLUDED.sender_kind,
                        sender_display_name = EXCLUDED.sender_display_name,
                        role = EXCLUDED.role,
                        content = EXCLUDED.content
                    """
                ),
                {
                    "id": str(message.id),
                    "conversation_id": str(message.conversation_id),
                    "sender_id": str(message.sender.id),
                    "sender_kind": message.sender.kind.value,
                    "sender_display_name": message.sender.display_name,
                    "role": message.role.value,
                    "content": message.content,
                    "created_at": message.created_at,
                },
            )
        return message

    def find_by_conversation(
        self,
        conversation_id: uuid.UUID,
        *,
        limit: int = 100,
        before: datetime | None = None,
    ) -> list[Message]:
        with self._engine.connect() as conn:
            params: dict[str, object] = {"conversation_id": str(conversation_id), "limit": limit}
            if before is None:
                rows = conn.execute(
                    text(
                        f"""
                        SELECT * FROM {self._messages_table_name}
                        WHERE conversation_id = :conversation_id
                        ORDER BY created_at DESC
                        LIMIT :limit
                        """
                    ),
                    params,
                ).fetchall()
            else:
                params["before"] = before
                rows = conn.execute(
                    text(
                        f"""
                        SELECT * FROM {self._messages_table_name}
                        WHERE conversation_id = :conversation_id AND created_at < :before
                        ORDER BY created_at DESC
                        LIMIT :limit
                        """
                    ),
                    params,
                ).fetchall()
        return [_row_to_message(row) for row in rows]

    def delete_by_conversation(self, conversation_id: uuid.UUID) -> int:
        with self._engine.begin() as conn:
            result = conn.execute(
                text(f"DELETE FROM {self._messages_table_name} WHERE conversation_id = :conversation_id"),
                {"conversation_id": str(conversation_id)},
            )
        return result.rowcount


def _parse_uuid(value: object) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def _ensure_datetime(value: datetime | str) -> datetime:
    converted = datetime.fromisoformat(value) if isinstance(value, str) else value
    if converted.tzinfo is None:
        converted = converted.replace(tzinfo=timezone.utc)
    return converted


def _row_to_message(row) -> Message:
    return Message(
        id=_parse_uuid(row.id),
        conversation_id=_parse_uuid(row.conversation_id),
        sender=Participant(
            id=_parse_uuid(row.sender_id),
            kind=ParticipantKind(row.sender_kind),
            display_name=row.sender_display_name,
        ),
        role=MessageRole(row.role),
        content=row.content,
        created_at=_ensure_datetime(row.created_at),
    )
