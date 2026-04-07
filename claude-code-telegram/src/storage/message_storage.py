"""Message history storage for persistent conversations.

This module provides storage for conversation history to enable
persistent context across multiple interactions with the local
Bun-based Claude implementation.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Dict, List, Optional

import aiosqlite
import structlog

logger = structlog.get_logger()


class MessageRole(Enum):
    """Message role in conversation."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class ConversationMessage:
    """A single message in the conversation."""

    id: Optional[int]
    session_id: str
    role: MessageRole
    content: str
    timestamp: datetime
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_row(cls, row: aiosqlite.Row) -> "ConversationMessage":
        """Create from database row."""
        return cls(
            id=row["id"],
            session_id=row["session_id"],
            role=MessageRole(row["role"]),
            content=row["content"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )


class MessageHistoryStorage:
    """Storage for conversation message history."""

    def __init__(self, db_path: str = "data/bot.db"):
        """Initialize message storage.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path

    async def _get_db(self) -> aiosqlite.Connection:
        """Get database connection."""
        db = await aiosqlite.connect(self.db_path)
        db.row_factory = aiosqlite.Row
        return db

    async def initialize(self) -> None:
        """Initialize database tables."""
        async with await self._get_db() as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}',
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
                )
                """
            )
            await db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_messages_session 
                ON conversation_messages(session_id, timestamp)
                """
            )
            await db.commit()
            logger.info("Message history table initialized")

    async def add_message(
        self,
        session_id: str,
        role: MessageRole,
        content: str,
        metadata: Optional[Dict] = None,
    ) -> ConversationMessage:
        """Add a message to the conversation history.

        Args:
            session_id: Session identifier
            role: Message role (user/assistant/system)
            content: Message content
            metadata: Optional metadata

        Returns:
            Created message
        """
        timestamp = datetime.now(UTC)
        meta_json = json.dumps(metadata or {})

        async with await self._get_db() as db:
            cursor = await db.execute(
                """
                INSERT INTO conversation_messages 
                (session_id, role, content, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, role.value, content, timestamp.isoformat(), meta_json),
            )
            await db.commit()

            message = ConversationMessage(
                id=cursor.lastrowid,
                session_id=session_id,
                role=role,
                content=content,
                timestamp=timestamp,
                metadata=metadata or {},
            )

            logger.debug(
                "Message added to history",
                session_id=session_id,
                role=role.value,
                message_id=cursor.lastrowid,
            )

            return message

    async def get_conversation_history(
        self,
        session_id: str,
        limit: int = 100,
        before_message_id: Optional[int] = None,
    ) -> List[ConversationMessage]:
        """Get conversation history for a session.

        Args:
            session_id: Session identifier
            limit: Maximum number of messages to return
            before_message_id: If set, only return messages before this ID

        Returns:
            List of messages in chronological order
        """
        async with await self._get_db() as db:
            if before_message_id:
                cursor = await db.execute(
                    """
                    SELECT * FROM conversation_messages
                    WHERE session_id = ? AND id < ?
                    ORDER BY timestamp ASC
                    LIMIT ?
                    """,
                    (session_id, before_message_id, limit),
                )
            else:
                cursor = await db.execute(
                    """
                    SELECT * FROM conversation_messages
                    WHERE session_id = ?
                    ORDER BY timestamp ASC
                    LIMIT ?
                    """,
                    (session_id, limit),
                )

            rows = await cursor.fetchall()
            messages = [ConversationMessage.from_row(row) for row in rows]

            logger.debug(
                "Retrieved conversation history",
                session_id=session_id,
                message_count=len(messages),
            )

            return messages

    async def get_message_count(self, session_id: str) -> int:
        """Get total message count for a session."""
        async with await self._get_db() as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM conversation_messages WHERE session_id = ?",
                (session_id,),
            )
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def delete_session_messages(self, session_id: str) -> int:
        """Delete all messages for a session.

        Returns:
            Number of messages deleted
        """
        async with await self._get_db() as db:
            cursor = await db.execute(
                "DELETE FROM conversation_messages WHERE session_id = ?",
                (session_id,),
            )
            await db.commit()

            deleted_count = cursor.rowcount
            logger.info(
                "Session messages deleted",
                session_id=session_id,
                deleted_count=deleted_count,
            )

            return deleted_count

    async def trim_conversation(
        self,
        session_id: str,
        keep_last: int = 50,
    ) -> int:
        """Trim conversation to keep only the last N messages.

        This is useful for preventing context window overflow.

        Args:
            session_id: Session identifier
            keep_last: Number of recent messages to keep

        Returns:
            Number of messages deleted
        """
        async with await self._get_db() as db:
            # Get the ID of the Nth most recent message
            cursor = await db.execute(
                """
                SELECT id FROM conversation_messages
                WHERE session_id = ?
                ORDER BY timestamp DESC
                LIMIT 1 OFFSET ?
                """,
                (session_id, keep_last),
            )
            row = await cursor.fetchone()

            if not row:
                # Less than keep_last messages, nothing to trim
                return 0

            cutoff_id = row["id"]

            # Delete all messages before this ID
            cursor = await db.execute(
                """
                DELETE FROM conversation_messages
                WHERE session_id = ? AND id < ?
                """,
                (session_id, cutoff_id),
            )
            await db.commit()

            deleted_count = cursor.rowcount
            logger.info(
                "Conversation trimmed",
                session_id=session_id,
                keep_last=keep_last,
                deleted_count=deleted_count,
            )

            return deleted_count


import json  # noqa: E402
