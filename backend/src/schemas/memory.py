"""
Memory-related Pydantic schemas.
"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID


class Learning(BaseModel):
    """A stored learning/memory."""
    id: Optional[UUID] = None
    content: str
    agent_name: str
    learning_type: str  # 'pattern', 'insight', 'rule', 'preference'
    confidence_score: float = Field(ge=0.0, le=1.0)
    source_session_id: Optional[UUID] = None
    created_at: datetime
    metadata: Optional[Dict[str, Any]] = None


class LearningCreate(BaseModel):
    """Create a new learning."""
    content: str
    agent_name: str
    learning_type: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    source_session_id: Optional[UUID] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LearningWithSimilarity(Learning):
    """Learning with similarity score from vector search."""
    similarity: float = Field(ge=0.0, le=1.0)


class MemorySearchRequest(BaseModel):
    """Request to search memories."""
    query: str
    agent_name: Optional[str] = None
    learning_type: Optional[str] = None
    top_k: int = Field(default=5, ge=1, le=50)
    min_similarity: float = Field(default=0.7, ge=0.0, le=1.0)
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class MemorySearchResponse(BaseModel):
    """Response from memory search."""
    query: str
    results: List[LearningWithSimilarity]
    search_time_ms: int


class WorkingMemory(BaseModel):
    """Working memory context for a user."""
    user_id: str
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    key_facts: List[str] = Field(default_factory=list)
    current_focus: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SessionMemory(BaseModel):
    """Complete memory context for a session."""
    session_id: UUID
    messages: List[Dict[str, Any]]
    relevant_learnings: List[LearningWithSimilarity] = Field(default_factory=list)
    working_memory: Optional[WorkingMemory] = None
