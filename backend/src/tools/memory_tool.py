"""
Memory retrieval tool for agents to access relevant past learnings and context.
"""
from typing import List, Optional, Dict, Any
from uuid import UUID

from ..memory.vector_store import vector_store
from ..memory.session_manager import session_manager
from ..core.telemetry import get_logger
from ..schemas.memory import LearningWithSimilarity, SessionMemory, WorkingMemory
from ..schemas.chat import ChatMessage


logger = get_logger(__name__)


class MemoryRetrievalTool:
    """
    Tool for retrieving relevant memories for agent context.

    Combines:
    - Semantic search (vector similarity)
    - Recent session history
    - Working memory context
    """

    async def retrieve_context(
        self,
        query: str,
        session_id: UUID,
        agent_name: str,
        top_k: int = 5,
        min_similarity: float = 0.7,
        include_session_history: bool = True,
        max_history_messages: int = 10,
    ) -> SessionMemory:
        """
        Retrieve relevant memory context for an agent.

        Args:
            query: Query text for semantic search
            session_id: Current session ID
            agent_name: Agent requesting memory
            top_k: Number of similar learnings to retrieve
            min_similarity: Minimum similarity threshold
            include_session_history: Whether to include recent messages
            max_history_messages: Max messages to include from history

        Returns:
            SessionMemory with relevant context
        """
        logger.info(
            "Retrieving memory context",
            agent_name=agent_name,
            session_id=str(session_id),
            query_preview=query[:50],
        )

        # 1. Get relevant learnings via semantic search
        relevant_learnings = await vector_store.search_similar(
            query=query,
            agent_name=None,  # Search across all agents
            top_k=top_k,
            min_similarity=min_similarity,
        )

        logger.info(
            "Retrieved semantic memories",
            count=len(relevant_learnings),
        )

        # 2. Get recent session history
        messages = []
        if include_session_history:
            messages_objs = await session_manager.get_messages(
                session_id=session_id,
                limit=max_history_messages,
            )
            messages = [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "agent_name": msg.agent_name,
                    "timestamp": msg.timestamp.isoformat(),
                }
                for msg in messages_objs
            ]

        logger.info(
            "Retrieved session history",
            message_count=len(messages),
        )

        # 3. Build session memory
        session_memory = SessionMemory(
            session_id=session_id,
            messages=messages,
            relevant_learnings=relevant_learnings,
        )

        return session_memory

    async def retrieve_learnings_by_type(
        self,
        learning_type: str,
        agent_name: Optional[str] = None,
        min_confidence: float = 0.7,
        limit: int = 10,
    ) -> List[LearningWithSimilarity]:
        """
        Retrieve learnings by type (pattern, insight, rule, preference).

        Args:
            learning_type: Type of learning to retrieve
            agent_name: Filter by agent (optional)
            min_confidence: Minimum confidence score
            limit: Max results to return

        Returns:
            List of relevant learnings
        """
        logger.info(
            "Retrieving learnings by type",
            learning_type=learning_type,
            agent_name=agent_name,
        )

        # Use a generic query to get learnings of this type
        # The similarity will be lower, but we're filtering by type and confidence
        learnings = await vector_store.search_similar(
            query=f"{learning_type} learning",
            agent_name=agent_name,
            learning_type=learning_type,
            top_k=limit,
            min_similarity=0.0,  # Don't filter by similarity here
            min_confidence=min_confidence,
        )

        logger.info(
            "Retrieved learnings",
            count=len(learnings),
        )

        return learnings

    async def get_agent_expertise(
        self,
        agent_name: str,
        top_k: int = 5,
    ) -> List[LearningWithSimilarity]:
        """
        Get the top learnings/expertise for a specific agent.

        Useful for understanding what an agent knows best.

        Args:
            agent_name: Agent to get expertise for
            top_k: Number of top learnings

        Returns:
            Top learnings by confidence score
        """
        logger.info(
            "Retrieving agent expertise",
            agent_name=agent_name,
        )

        # Get high-confidence learnings for this agent
        learnings = await vector_store.search_similar(
            query=f"{agent_name} expertise",
            agent_name=agent_name,
            top_k=top_k,
            min_similarity=0.0,
            min_confidence=0.8,  # High confidence only
        )

        return learnings

    async def build_context_summary(
        self,
        session_memory: SessionMemory,
    ) -> str:
        """
        Build a text summary of memory context for LLM consumption.

        Args:
            session_memory: Session memory to summarize

        Returns:
            Formatted context string
        """
        parts = []

        # Add relevant learnings
        if session_memory.relevant_learnings:
            parts.append("## Relevant Past Learnings")
            for i, learning in enumerate(session_memory.relevant_learnings, 1):
                parts.append(
                    f"{i}. [{learning.learning_type}] {learning.content} "
                    f"(confidence: {learning.confidence_score:.2f}, "
                    f"similarity: {learning.similarity:.2f})"
                )
            parts.append("")

        # Add recent conversation
        if session_memory.messages:
            parts.append("## Recent Conversation")
            for msg in session_memory.messages[-5:]:  # Last 5 messages
                role = msg["role"].upper()
                agent = f" ({msg['agent_name']})" if msg.get("agent_name") else ""
                parts.append(f"{role}{agent}: {msg['content']}")
            parts.append("")

        return "\n".join(parts)


# Global instance
memory_retrieval_tool = MemoryRetrievalTool()
