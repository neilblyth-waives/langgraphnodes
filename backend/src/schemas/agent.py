"""
Agent-related Pydantic schemas.
"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID


class AgentState(BaseModel):
    """Base state for agent graph."""
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    session_id: Optional[UUID] = None
    user_id: str
    current_agent: Optional[str] = None
    next_agent: Optional[str] = None
    final_response: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentInput(BaseModel):
    """Input to an agent."""
    message: str
    session_id: Optional[UUID] = None
    user_id: str
    context: Dict[str, Any] = Field(default_factory=dict)


class AgentOutput(BaseModel):
    """Output from an agent."""
    response: str
    agent_name: str
    reasoning: Optional[str] = None
    tools_used: List[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentDecision(BaseModel):
    """Record of an agent decision."""
    id: Optional[UUID] = None
    session_id: UUID
    message_id: Optional[UUID] = None
    agent_name: str
    decision_type: str
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    tools_used: List[str]
    reasoning: str
    timestamp: datetime
    execution_time_ms: int


class AgentDecisionCreate(BaseModel):
    """Create an agent decision record."""
    session_id: UUID
    message_id: Optional[UUID] = None
    agent_name: str
    decision_type: str
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    tools_used: List[str] = Field(default_factory=list)
    reasoning: str
    execution_time_ms: int


class ToolCall(BaseModel):
    """Record of a tool call."""
    tool_name: str
    input_params: Dict[str, Any]
    output: Any
    execution_time_ms: int
    success: bool
    error: Optional[str] = None
