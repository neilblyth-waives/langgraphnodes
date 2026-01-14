"""
Session manager for handling conversation sessions and message history.
"""
from typing import Dict, List, Optional, Any
from uuid import UUID, uuid4
from datetime import datetime
import time
import json

from ..core.database import get_pg_connection
from ..core.cache import set_session, get_session, extend_session
from ..core.telemetry import get_logger, log_db_query
from ..schemas.chat import ChatMessage, ChatMessageCreate, SessionInfo


logger = get_logger(__name__)


class SessionManager:
    """
    Manages conversation sessions and message history.

    Features:
    - Create and manage sessions
    - Store and retrieve message history
    - Session persistence in database + Redis cache
    - Automatic TTL management
    """

    async def create_session(
        self,
        user_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> UUID:
        """
        Create a new session.

        Args:
            user_id: User identifier
            metadata: Optional metadata

        Returns:
            Session ID
        """
        start_time = time.time()

        try:
            session_id = uuid4()

            async with get_pg_connection() as conn:
                query = """
                    INSERT INTO sessions (id, user_id, metadata)
                    VALUES ($1, $2, $3)
                    RETURNING id
                """

                await conn.fetchval(
                    query,
                    session_id,
                    user_id,
                    json.dumps(metadata or {}),
                )

                duration = time.time() - start_time
                log_db_query("insert", "sessions", duration)

                # Don't cache here - let get_session_info() handle caching with complete data

                logger.info(
                    "Session created",
                    session_id=str(session_id),
                    user_id=user_id,
                )

                return session_id

        except Exception as e:
            duration = time.time() - start_time
            log_db_query("insert", "sessions", duration, error=str(e))
            logger.error("Failed to create session", error=str(e))
            raise

    async def get_session_info(self, session_id: UUID) -> Optional[SessionInfo]:
        """
        Get session information.

        Args:
            session_id: Session ID

        Returns:
            Session info or None if not found
        """
        start_time = time.time()

        try:
            # Check cache first
            cached = await get_session(str(session_id))
            if cached:
                # Handle legacy cache format with 'session_id' instead of 'id'
                if 'session_id' in cached and 'id' not in cached:
                    cached['id'] = cached.pop('session_id')
                return SessionInfo(**cached)

            # Get from database
            async with get_pg_connection() as conn:
                query = """
                    SELECT
                        s.id,
                        s.user_id,
                        s.created_at,
                        s.updated_at,
                        s.metadata,
                        COUNT(m.id) as message_count
                    FROM sessions s
                    LEFT JOIN messages m ON s.id = m.session_id
                    WHERE s.id = $1
                    GROUP BY s.id, s.user_id, s.created_at, s.updated_at, s.metadata
                """

                row = await conn.fetchrow(query, session_id)

                duration = time.time() - start_time
                log_db_query("select", "sessions", duration)

                if not row:
                    return None

                session_info = SessionInfo(
                    id=row["id"],
                    user_id=row["user_id"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    message_count=row["message_count"],
                    metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                )

                # Cache for future requests
                await set_session(str(session_id), session_info.model_dump(mode='json'))

                return session_info

        except Exception as e:
            duration = time.time() - start_time
            log_db_query("select", "sessions", duration, error=str(e))
            logger.error("Failed to get session info", error=str(e))
            raise

    async def add_message(self, message: ChatMessageCreate) -> UUID:
        """
        Add a message to a session.

        Args:
            message: Message to add

        Returns:
            Message ID
        """
        start_time = time.time()

        try:
            async with get_pg_connection() as conn:
                query = """
                    INSERT INTO messages (
                        session_id,
                        role,
                        content,
                        agent_name,
                        metadata
                    )
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING id
                """

                message_id = await conn.fetchval(
                    query,
                    message.session_id,
                    message.role,
                    message.content,
                    message.agent_name,
                    json.dumps(message.metadata) if message.metadata else None,
                )

                # Update session updated_at
                await conn.execute(
                    "UPDATE sessions SET updated_at = NOW() WHERE id = $1",
                    message.session_id
                )

                duration = time.time() - start_time
                log_db_query("insert", "messages", duration)

                # Extend session TTL
                await extend_session(str(message.session_id))

                logger.info(
                    "Message added",
                    message_id=str(message_id),
                    session_id=str(message.session_id),
                    role=message.role,
                )

                return message_id

        except Exception as e:
            duration = time.time() - start_time
            log_db_query("insert", "messages", duration, error=str(e))
            logger.error("Failed to add message", error=str(e))
            raise

    async def get_messages(
        self,
        session_id: UUID,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[ChatMessage]:
        """
        Get messages for a session.

        Args:
            session_id: Session ID
            limit: Optional limit on number of messages
            offset: Offset for pagination

        Returns:
            List of messages
        """
        start_time = time.time()

        try:
            async with get_pg_connection() as conn:
                if limit:
                    query = """
                        SELECT id, session_id, role, content, agent_name, timestamp, metadata
                        FROM messages
                        WHERE session_id = $1
                        ORDER BY timestamp ASC
                        LIMIT $2 OFFSET $3
                    """
                    rows = await conn.fetch(query, session_id, limit, offset)
                else:
                    query = """
                        SELECT id, session_id, role, content, agent_name, timestamp, metadata
                        FROM messages
                        WHERE session_id = $1
                        ORDER BY timestamp ASC
                    """
                    rows = await conn.fetch(query, session_id)

                duration = time.time() - start_time
                log_db_query("select", "messages", duration)

                messages = [
                    ChatMessage(
                        id=row["id"],
                        session_id=row["session_id"],
                        role=row["role"],
                        content=row["content"],
                        agent_name=row["agent_name"],
                        timestamp=row["timestamp"],
                        metadata=json.loads(row["metadata"]) if row["metadata"] else None,
                    )
                    for row in rows
                ]

                return messages

        except Exception as e:
            duration = time.time() - start_time
            log_db_query("select", "messages", duration, error=str(e))
            logger.error("Failed to get messages", error=str(e))
            raise

    async def get_user_sessions(
        self,
        user_id: str,
        limit: int = 10,
        offset: int = 0
    ) -> List[SessionInfo]:
        """
        Get sessions for a user.

        Args:
            user_id: User ID
            limit: Maximum number of sessions
            offset: Offset for pagination

        Returns:
            List of session info
        """
        start_time = time.time()

        try:
            async with get_pg_connection() as conn:
                query = """
                    SELECT
                        s.id,
                        s.user_id,
                        s.created_at,
                        s.updated_at,
                        s.metadata,
                        COUNT(m.id) as message_count
                    FROM sessions s
                    LEFT JOIN messages m ON s.id = m.session_id
                    WHERE s.user_id = $1
                    GROUP BY s.id, s.user_id, s.created_at, s.updated_at, s.metadata
                    ORDER BY s.updated_at DESC
                    LIMIT $2 OFFSET $3
                """

                rows = await conn.fetch(query, user_id, limit, offset)

                duration = time.time() - start_time
                log_db_query("select", "sessions", duration)

                sessions = [
                    SessionInfo(
                        id=row["id"],
                        user_id=row["user_id"],
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                        message_count=row["message_count"],
                        metadata=row["metadata"],
                    )
                    for row in rows
                ]

                return sessions

        except Exception as e:
            duration = time.time() - start_time
            log_db_query("select", "sessions", duration, error=str(e))
            logger.error("Failed to get user sessions", error=str(e))
            raise


# Global instance
session_manager = SessionManager()
