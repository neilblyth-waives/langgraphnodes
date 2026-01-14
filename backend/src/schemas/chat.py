"""
Chat-related Pydantic schemas.
"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID


class ChatMessage(BaseModel):
    """A chat message."""
    id: Optional[UUID] = None
    session_id: UUID
    role: str  # 'user', 'assistant', 'agent'
    content: str
    agent_name: Optional[str] = None
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None


class ChatMessageCreate(BaseModel):
    """Create a chat message."""
    session_id: UUID
    role: str
    content: str
    agent_name: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    """Request to send a chat message."""
    message: str
    session_id: Optional[UUID] = None
    user_id: str = Field(default="default_user")
    stream: bool = Field(default=False)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    """Response from chat endpoint."""
    session_id: UUID
    message_id: UUID
    response: str
    agent_name: str
    reasoning: Optional[str] = None
    tools_used: List[str] = Field(default_factory=list)
    execution_time_ms: int
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SessionInfo(BaseModel):
    """Session information."""
    model_config = {"populate_by_name": True}

    id: UUID
    user_id: str
    created_at: datetime
    updated_at: datetime
    message_count: int
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SessionCreate(BaseModel):
    """Create a new session."""
    user_id: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SessionHistory(BaseModel):
    """Session with full message history."""
    session: SessionInfo
    messages: List[ChatMessage]


class StreamChunk(BaseModel):
    """A chunk of streaming response."""
    type: str  # 'token', 'agent', 'tool', 'complete', 'error'
    content: str
    agent_name: Optional[str] = None
    tool_name: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
