"""
Chat API with streaming progress and session persistence.
"""
import time
import json
import asyncio
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, AsyncGenerator
from uuid import UUID

from ...agents.supervisor import supervisor, super_graph
from ...schemas.agent import AgentInput
from ...core.session_manager import (
    get_or_create_session,
    load_session_messages,
    save_messages_from_state
)
from langchain_core.messages import HumanMessage

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[UUID] = None
    user_id: str = "default_user"


class ChatResponse(BaseModel):
    response: str
    session_id: UUID
    execution_time_ms: int


@router.post("/", response_model=ChatResponse)
async def send_message(request: ChatRequest):
    """Chat endpoint with session persistence."""
    start_time = time.time()
    
    # Get or create session
    session_id = await get_or_create_session(
        user_id=request.user_id,
        session_id=request.session_id
    )
    
    # Load previous messages from session
    previous_messages = await load_session_messages(session_id)
    
    # Call supervisor with full message history
    # Messages are automatically saved to database by supervisor.invoke
    output = await supervisor.invoke(
        agent_input=AgentInput(
            message=request.message,
            session_id=session_id,
            user_id=request.user_id
        ),
        previous_messages=previous_messages
    )
    
    execution_time_ms = int((time.time() - start_time) * 1000)
    
    return ChatResponse(
        response=output.response,
        session_id=session_id,
        execution_time_ms=execution_time_ms
    )


@router.post("/stream")
async def stream_message(request: ChatRequest):
    """Streaming chat endpoint with real-time progress updates."""

    async def event_generator() -> AsyncGenerator[str, None]:
        start_time = time.time()

        try:
            # Get or create session
            session_id = await get_or_create_session(
                user_id=request.user_id,
                session_id=request.session_id
            )

            # Load previous messages
            previous_messages = await load_session_messages(session_id)

            # Build initial state
            initial_messages = []
            if previous_messages:
                initial_messages.extend(previous_messages)
            initial_messages.append(HumanMessage(content=request.message))

            initial_state = {
                "messages": initial_messages,
                "next": None,
                "session_id": session_id,
                "user_id": request.user_id,
                "iteration_count": 0,
                "agents_called": [],
                "budget_complete": False,
                "performance_complete": False
            }

            # Track node timing using astream_events for accurate start/end times
            node_start_times = {}
            final_state = dict(initial_state)

            # Stream graph execution with events for accurate timing
            async for event in super_graph.astream_events(initial_state, version="v2"):
                event_type = event.get("event")
                node_name = event.get("name")

                # Filter to only graph node events (not internal LLM/tool events)
                if event.get("metadata", {}).get("langgraph_node"):
                    node_name = event["metadata"]["langgraph_node"]

                    if event_type == "on_chain_start":
                        # Node is starting
                        node_start_times[node_name] = time.time()
                        yield f"data: {json.dumps({'type': 'progress', 'phase': node_name, 'status': 'started', 'message': get_phase_message(node_name)})}\n\n"

                    elif event_type == "on_chain_end":
                        # Node completed
                        start = node_start_times.get(node_name, time.time())
                        duration_ms = int((time.time() - start) * 1000)
                        yield f"data: {json.dumps({'type': 'progress', 'phase': node_name, 'status': 'completed', 'duration_ms': duration_ms})}\n\n"

                        # Update final state from output
                        output = event.get("data", {}).get("output", {})
                        if isinstance(output, dict):
                            for key, value in output.items():
                                if key == "messages" and isinstance(value, list):
                                    final_state.setdefault("messages", []).extend(value)
                                else:
                                    final_state[key] = value

            # Get final response
            execution_time_ms = int((time.time() - start_time) * 1000)
            messages = final_state.get("messages", []) if final_state else []
            final_response = messages[-1].content if messages else "No response"

            # Save messages to session
            if session_id and final_state:
                previous_content_set = {msg.content for msg in (previous_messages or []) if hasattr(msg, 'content')}
                new_messages = [
                    msg for msg in messages
                    if hasattr(msg, 'content') and msg.content not in previous_content_set
                ]
                if new_messages:
                    await save_messages_from_state(session_id=session_id, messages=new_messages)

            # Send complete event
            yield f"data: {json.dumps({'type': 'complete', 'data': {'response': final_response, 'session_id': str(session_id), 'execution_time_ms': execution_time_ms, 'agent_name': 'supervisor', 'confidence': 0.9, 'tools_used': []}})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


def get_phase_message(node_name: str) -> str:
    """Get human-readable message for each phase."""
    messages = {
        "supervisor": "Analyzing request and routing...",
        "budget": "Querying budget data...",
        "performance": "Analyzing performance metrics..."
    }
    return messages.get(node_name, f"Running {node_name}...")
