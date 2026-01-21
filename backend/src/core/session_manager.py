"""
Session and message persistence manager.
Handles loading and saving conversation history to PostgreSQL.
"""
from typing import List, Optional
from uuid import UUID, uuid4
from datetime import datetime
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

from .database import get_pg_connection, db_available
from .telemetry import get_logger

logger = get_logger(__name__)




async def get_or_create_session(user_id: str, session_id: Optional[UUID] = None) -> UUID:
    """Get existing session or create new one."""
    if not db_available:
        return session_id or uuid4()
    
    try:
        async with get_pg_connection() as conn:
            if session_id:
                # Check if session exists
                exists = await conn.fetchval(
                    "SELECT id FROM sessions WHERE id = $1",
                    session_id
                )
                if exists:
                    return session_id
            
            # Create new session
            new_session_id = await conn.fetchval(
                """
                INSERT INTO sessions (user_id, created_at, updated_at)
                VALUES ($1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                RETURNING id
                """,
                user_id
            )
            return new_session_id
    except Exception as e:
        logger.error("Failed to get/create session", error=str(e))
        return session_id or uuid4()


async def load_session_messages(session_id: UUID) -> List[BaseMessage]:
    """Load all messages from a session."""
    if not db_available:
        return []
    
    try:
        async with get_pg_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT role, content, agent_name, timestamp
                FROM messages
                WHERE session_id = $1
                ORDER BY timestamp ASC
                """,
                session_id
            )
            
            messages = []
            for row in rows:
                content = row['content']
                role = row['role']
                agent_name = row['agent_name']
                
                if role == 'user':
                    messages.append(HumanMessage(content=content))
                elif role == 'assistant':
                    # Use agent_name if available (for named messages)
                    if agent_name:
                        messages.append(AIMessage(content=content, name=agent_name))
                    else:
                        messages.append(AIMessage(content=content))
                elif role == 'system':
                    messages.append(SystemMessage(content=content))
            
            return messages
    except Exception as e:
        logger.error("Failed to load session messages", error=str(e), session_id=str(session_id))
        return []


async def save_message(
    session_id: UUID,
    role: str,
    content: str,
    agent_name: Optional[str] = None,
    metadata: Optional[dict] = None
) -> Optional[UUID]:
    """Save a message to the database."""
    if not db_available:
        return None
    
    try:
        async with get_pg_connection() as conn:
            message_id = await conn.fetchval(
                """
                INSERT INTO messages (session_id, role, content, agent_name, timestamp, metadata)
                VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP, $5)
                RETURNING id
                """,
                session_id,
                role,
                content,
                agent_name,
                metadata or {}
            )
            
            # Update session updated_at
            await conn.execute(
                "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = $1",
                session_id
            )
            
            return message_id
    except Exception as e:
        logger.error("Failed to save message", error=str(e), session_id=str(session_id))
        return None


async def save_messages_from_state(session_id: UUID, messages: List[BaseMessage]) -> None:
    """Save all new messages from state to database.
    
    Saves messages that aren't already in the database.
    Allows duplicate content if it's a separate user message (different request).
    """
    if not db_available:
        return
    
    try:
        # Get existing messages to check for duplicates
        existing_messages = await load_session_messages(session_id)
        
        # Create signatures of existing messages (content + role + agent_name)
        # This prevents saving the same message twice in one execution
        existing_signatures = set()
        for msg in existing_messages:
            if not hasattr(msg, 'content'):
                continue
            # Get content as string (handle structured formats)
            content_raw = msg.content
            if isinstance(content_raw, str):
                content = content_raw
            elif isinstance(content_raw, dict) and 'text' in content_raw:
                content = content_raw['text']
            elif isinstance(content_raw, list):
                content = " ".join(str(item.get('text', item) if isinstance(item, dict) else item) for item in content_raw)
            else:
                content = str(content_raw)
            
            role = 'user' if isinstance(msg, HumanMessage) else 'assistant' if isinstance(msg, AIMessage) else 'system'
            agent_name = getattr(msg, 'name', None) if isinstance(msg, AIMessage) else None
            
            sig = (content, role, agent_name)
            existing_signatures.add(sig)
        
        # Save only new messages
        saved_count = 0
        for msg in messages:
            if not hasattr(msg, 'content') or not msg.content:
                continue
            
            # Determine role and agent_name
            if isinstance(msg, HumanMessage):
                role = 'user'
                agent_name = None
            elif isinstance(msg, AIMessage):
                role = 'assistant'
                agent_name = getattr(msg, 'name', None) or 'supervisor'
            elif isinstance(msg, SystemMessage):
                role = 'system'
                agent_name = None
            else:
                continue
            
            # Get content as string (handle structured formats)
            content_raw = msg.content
            if isinstance(content_raw, str):
                content = content_raw
            elif isinstance(content_raw, dict) and 'text' in content_raw:
                content = content_raw['text']
            elif isinstance(content_raw, list):
                content = " ".join(str(item.get('text', item) if isinstance(item, dict) else item) for item in content_raw)
            else:
                content = str(content_raw)
            
            # Check if this exact message already exists
            msg_sig = (content, role, agent_name)
            
            # Always allow user messages (even if duplicate content - user can send same message multiple times)
            # Only skip duplicate assistant/system messages
            if msg_sig in existing_signatures and role != 'user':
                continue
            
            # Save the message
            await save_message(
                session_id=session_id,
                role=role,
                content=content,  # Use extracted text content
                agent_name=agent_name
            )
            
            existing_signatures.add(msg_sig)  # Track as saved
            saved_count += 1
            
    except Exception as e:
        logger.error("Failed to save messages from state", error=str(e), session_id=str(session_id))

