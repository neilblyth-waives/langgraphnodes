"""
Vector store implementation using pgvector for semantic memory.
"""
from typing import List, Optional
from uuid import UUID
import time
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

from openai import OpenAI
from langchain_openai import OpenAIEmbeddings

from ..core.config import settings
from ..core.database import get_pg_connection
from ..core.telemetry import get_logger, log_db_query
from ..schemas.memory import Learning, LearningCreate, LearningWithSimilarity


logger = get_logger(__name__)

# Thread pool for CPU-bound embedding operations
executor = ThreadPoolExecutor(max_workers=3)


class VectorStore:
    """
    Vector store for semantic memory using pgvector.

    Features:
    - Store learnings with embeddings
    - Semantic similarity search
    - Filtering by agent, type, confidence
    """

    def __init__(self):
        """Initialize vector store."""
        self.embeddings = self._initialize_embeddings()
        logger.info("Vector store initialized")

    def _initialize_embeddings(self):
        """
        Initialize embedding model.

        Note: Anthropic (Claude) doesn't provide embeddings.
        OpenAI is required for semantic memory (vector search).
        Recommended setup: ANTHROPIC_API_KEY (for LLM) + OPENAI_API_KEY (for embeddings)
        """
        if settings.openai_api_key:
            logger.info("Using OpenAI for embeddings", model=settings.openai_embedding_model)
            return OpenAIEmbeddings(
                model=settings.openai_embedding_model,
                api_key=settings.openai_api_key,
            )
        elif settings.anthropic_api_key:
            logger.warning(
                "Anthropic doesn't provide embeddings. "
                "Semantic memory disabled. "
                "Add OPENAI_API_KEY to enable vector search."
            )
            return None
        else:
            logger.warning("No embedding model configured, semantic search disabled")
            return None

    async def _get_embedding(self, text: str) -> List[float]:
        """
        Get embedding for text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        if not self.embeddings:
            return []

        try:
            # Run embedding in thread pool (can be CPU intensive)
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(
                executor,
                self.embeddings.embed_query,
                text
            )
            return embedding
        except Exception as e:
            logger.error(f"Failed to get embedding: {e}")
            return []

    async def store_learning(self, learning: LearningCreate) -> UUID:
        """
        Store a learning with its embedding.

        Args:
            learning: Learning to store

        Returns:
            UUID of stored learning
        """
        start_time = time.time()

        try:
            # Get embedding
            embedding = await self._get_embedding(learning.content)

            # Store in database
            async with get_pg_connection() as conn:
                query = """
                    INSERT INTO agent_learnings (
                        content,
                        embedding,
                        source_session_id,
                        agent_name,
                        learning_type,
                        confidence_score,
                        metadata
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    RETURNING id
                """

                # Convert embedding list to pgvector string format
                embedding_str = f"[{','.join(str(x) for x in embedding)}]" if embedding else None

                learning_id = await conn.fetchval(
                    query,
                    learning.content,
                    embedding_str,
                    learning.source_session_id,
                    learning.agent_name,
                    learning.learning_type,
                    learning.confidence_score,
                    json.dumps(learning.metadata) if learning.metadata else None,
                )

                duration = time.time() - start_time
                log_db_query("insert", "agent_learnings", duration)

                logger.info(
                    "Learning stored",
                    learning_id=str(learning_id),
                    agent_name=learning.agent_name,
                    learning_type=learning.learning_type,
                )

                return learning_id

        except Exception as e:
            duration = time.time() - start_time
            log_db_query("insert", "agent_learnings", duration, error=str(e))
            logger.error("Failed to store learning", error=str(e))
            raise

    async def search_similar(
        self,
        query: str,
        agent_name: Optional[str] = None,
        learning_type: Optional[str] = None,
        top_k: int = 5,
        min_similarity: float = 0.7,
        min_confidence: float = 0.0,
    ) -> List[LearningWithSimilarity]:
        """
        Search for similar learnings using vector similarity.

        Args:
            query: Search query
            agent_name: Optional filter by agent
            learning_type: Optional filter by learning type
            top_k: Number of results to return
            min_similarity: Minimum similarity threshold
            min_confidence: Minimum confidence threshold

        Returns:
            List of similar learnings with similarity scores
        """
        start_time = time.time()

        try:
            # Get query embedding
            query_embedding = await self._get_embedding(query)

            if not query_embedding:
                logger.warning("No embedding available, returning empty results")
                return []

            # Build query with filters
            async with get_pg_connection() as conn:
                # Convert query embedding to pgvector string format
                query_embedding_str = f"[{','.join(str(x) for x in query_embedding)}]"

                filters = ["1=1"]
                params = [query_embedding_str]
                param_idx = 2

                if agent_name:
                    filters.append(f"agent_name = ${param_idx}")
                    params.append(agent_name)
                    param_idx += 1

                if learning_type:
                    filters.append(f"learning_type = ${param_idx}")
                    params.append(learning_type)
                    param_idx += 1

                if min_confidence > 0:
                    filters.append(f"confidence_score >= ${param_idx}")
                    params.append(min_confidence)
                    param_idx += 1

                filters_str = " AND ".join(filters)

                query_sql = f"""
                    SELECT
                        id,
                        content,
                        agent_name,
                        learning_type,
                        confidence_score,
                        source_session_id,
                        created_at,
                        metadata,
                        1 - (embedding <=> $1::vector) as similarity
                    FROM agent_learnings
                    WHERE {filters_str}
                      AND embedding IS NOT NULL
                      AND (1 - (embedding <=> $1::vector)) >= ${param_idx}
                    ORDER BY embedding <=> $1::vector
                    LIMIT ${param_idx + 1}
                """

                params.extend([min_similarity, top_k])

                rows = await conn.fetch(query_sql, *params)

                duration = time.time() - start_time
                log_db_query("select", "agent_learnings", duration)

                results = []
                for row in rows:
                    learning = LearningWithSimilarity(
                        id=row["id"],
                        content=row["content"],
                        agent_name=row["agent_name"],
                        learning_type=row["learning_type"],
                        confidence_score=row["confidence_score"],
                        source_session_id=row["source_session_id"],
                        created_at=row["created_at"],
                        metadata=json.loads(row["metadata"]) if row["metadata"] else None,
                        similarity=float(row["similarity"]),
                    )
                    results.append(learning)

                logger.info(
                    "Similarity search completed",
                    results_count=len(results),
                    duration_seconds=round(duration, 2),
                )

                return results

        except Exception as e:
            duration = time.time() - start_time
            log_db_query("select", "agent_learnings", duration, error=str(e))
            logger.error("Failed to search similar learnings", error=str(e))
            raise

    async def get_recent_learnings(
        self,
        agent_name: Optional[str] = None,
        learning_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[Learning]:
        """
        Get recent learnings.

        Args:
            agent_name: Optional filter by agent
            learning_type: Optional filter by learning type
            limit: Maximum number of results

        Returns:
            List of recent learnings
        """
        start_time = time.time()

        try:
            async with get_pg_connection() as conn:
                filters = []
                params = []
                param_idx = 1

                if agent_name:
                    filters.append(f"agent_name = ${param_idx}")
                    params.append(agent_name)
                    param_idx += 1

                if learning_type:
                    filters.append(f"learning_type = ${param_idx}")
                    params.append(learning_type)
                    param_idx += 1

                where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
                params.append(limit)

                query = f"""
                    SELECT
                        id,
                        content,
                        agent_name,
                        learning_type,
                        confidence_score,
                        source_session_id,
                        created_at,
                        metadata
                    FROM agent_learnings
                    {where_clause}
                    ORDER BY created_at DESC
                    LIMIT ${param_idx}
                """

                rows = await conn.fetch(query, *params)

                duration = time.time() - start_time
                log_db_query("select", "agent_learnings", duration)

                results = [
                    Learning(
                        id=row["id"],
                        content=row["content"],
                        agent_name=row["agent_name"],
                        learning_type=row["learning_type"],
                        confidence_score=row["confidence_score"],
                        source_session_id=row["source_session_id"],
                        created_at=row["created_at"],
                        metadata=row["metadata"],
                    )
                    for row in rows
                ]

                return results

        except Exception as e:
            duration = time.time() - start_time
            log_db_query("select", "agent_learnings", duration, error=str(e))
            logger.error("Failed to get recent learnings", error=str(e))
            raise


# Global instance
vector_store = VectorStore()
