"""
State definitions for LangGraph agents.

These TypedDict classes define the state schema that flows through
agent nodes in LangGraph workflows.
"""
from typing import TypedDict, Optional, List, Annotated, Literal
from uuid import UUID
import operator
from langgraph.graph import MessagesState
from langchain_core.messages import BaseMessage


class State(MessagesState):
    """
    State for Supervisor agent with conversational loop.
    
    Uses MessagesState to track conversation history.
    MessagesState automatically uses operator.add to merge messages (append, not replace).
    Agents and supervisor can go back and forth until supervisor is satisfied.
    """
    # MessagesState already defines 'messages' field with proper reducer
    # It uses operator.add which means messages are appended, not replaced
    next: str  # Next agent to call: "budget", "performance", or "FINISH"
    session_id: Optional[UUID]
    user_id: str
    iteration_count: int = 0  # Track supervisor iterations to prevent loops
    agents_called: List[str] = []  # Track which agents have been called
    budget_complete: bool = False  # Flag if budget agent completed task
    performance_complete: bool = False  # Flag if performance agent completed task
