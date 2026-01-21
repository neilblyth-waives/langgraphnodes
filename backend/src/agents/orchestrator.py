"""
Orchestrator - Main coordinator using RouteFlow architecture.

This orchestrator replaces the Chat Conductor and implements the full
RouteFlow architecture with routing, gate, diagnosis, early exit,
recommendation, and validation phases.
"""
from typing import Dict, Any, Callable, Awaitable, Optional
from uuid import UUID
import time
import asyncio

from langgraph.graph import StateGraph, END

# Type alias for progress callback
ProgressCallback = Callable[[str, str, Dict[str, Any]], Awaitable[None]]

from .base import BaseAgent
from .gate_node import gate_node
from ..memory.session_manager import session_manager
from .diagnosis_recommendation_agent import diagnosis_recommendation_agent
from .early_exit_node import early_exit_node
from .validation_agent import validation_agent

# Import specialist agents (simplified ReAct versions)
from .performance_agent_simple import performance_agent_simple
from .audience_agent_simple import audience_agent_simple
from .creative_agent_simple import creative_agent_simple
from .budget_risk_agent import budget_risk_agent
# Legacy agents (kept for backward compatibility)
from .delivery_agent_langgraph import delivery_agent_langgraph

from ..schemas.agent import AgentInput, AgentOutput
from ..schemas.agent_state import OrchestratorState, create_initial_orchestrator_state
from ..tools.memory_tool import memory_retrieval_tool
from ..core.telemetry import get_logger


logger = get_logger(__name__)


class Orchestrator(BaseAgent):
    """
    Orchestrator using RouteFlow architecture.

    Flow:
    1. routing → Intelligent LLM-based routing
    2. gate → Validation and business rules
    3. invoke_agents → Parallel specialist agent execution
    4. diagnosis → Root cause analysis
    5. early_exit_check → Conditional exit if no recommendations needed
    6. recommendation → Generate recommendations
    7. validation → Validate recommendations
    8. generate_response → Final response generation
    """

    def __init__(self):
        """Initialize Orchestrator."""
        super().__init__(
            agent_name="orchestrator",
            description="Main orchestrator for routing and coordinating specialist agents",
            tools=[],
        )

        # Registry of specialist agents (simplified ReAct versions)
        self.specialist_agents = {
            "performance_diagnosis": performance_agent_simple,  # IO-level metrics
            "audience_targeting": audience_agent_simple,        # Line item metrics
            "creative_inventory": creative_agent_simple,        # Creative name/size
            "budget_risk": budget_risk_agent,                   # Budget pacing
            "delivery_optimization": delivery_agent_langgraph,  # Legacy combined agent
        }

        # Build LangGraph
        self.graph = self._build_graph()

        # Progress callback (set during invoke_with_progress)
        self._progress_callback: Optional[ProgressCallback] = None
        self._start_time: float = 0

    def get_system_prompt(self) -> str:
        """Return system prompt."""
        from datetime import datetime
        current_date = datetime.now().strftime("%B %Y")
        current_year = datetime.now().year
        
        return f"""You are the Orchestrator Coordinator for a DV360 analysis system.

You are responsible for:
1. Analyzing user queries to understand intent
2. Deciding which specialist agents to use
3. Extracting and normalizing query parameters (time periods, dates, filters)
4. Coordinating agent execution with consistent parameters
5. Reviewing agent results for consistency
6. Coordinating diagnosis and recommendations

IMPORTANT: The current date is {current_date} (year {current_year}). All date references should be interpreted relative to {current_year} unless explicitly stated otherwise."""

    def _build_agent_message(
        self,
        agent_name: str,
        user_query: str,
        strategy: Dict[str, Any],
        normalized_params: Dict[str, Any]
    ) -> str:
        """
        Build an enhanced message for a specialist agent with explicit orchestrator instructions.
        
        This makes it clear to each agent:
        1. Their role in the coordinated analysis
        2. What the orchestrator needs from them specifically
        3. The normalized parameters to use (dates, time periods)
        4. Whether they're part of a comparison/multi-agent analysis
        """
        intent = strategy.get("intent", "")
        selected_agents = strategy.get("selected_agents", [])
        comparison_mode = strategy.get("comparison_mode", False)
        time_period = normalized_params.get("time_period", "")
        start_date = normalized_params.get("start_date", "")
        end_date = normalized_params.get("end_date", "")
        
        # Build agent role context
        agent_role_map = {
            "budget_risk": "budget analysis and pacing assessment",
            "performance_diagnosis": "campaign performance metrics and ROAS analysis",
            "audience_targeting": "audience performance and targeting insights",
            "creative_inventory": "creative effectiveness and inventory analysis",
            "delivery_optimization": "delivery optimization and pacing analysis"
        }
        agent_role = agent_role_map.get(agent_name, "specialized analysis")
        
        # Build time period context
        time_context = ""
        if start_date and end_date:
            time_context = f"Query data from {start_date} to {end_date} (inclusive, excluding today's date)."
        elif time_period:
            time_context = f"Focus on the time period: {time_period}."
            if time_period == "current_month":
                time_context += " Query current month data (excluding today's date)."
            elif time_period.startswith("last_"):
                days = time_period.replace("last_", "").replace("_days", "")
                time_context += f" Query the last {days} days of data (excluding today's date)."
        
        # Build coordination context
        coordination_context = ""
        if len(selected_agents) > 1:
            other_agents = [a for a in selected_agents if a != agent_name]
            coordination_context = f"\n\nCOORDINATED ANALYSIS:\n"
            coordination_context += f"- You are part of a coordinated analysis involving {len(selected_agents)} agents: {', '.join(selected_agents)}\n"
            coordination_context += f"- Other agents ({', '.join(other_agents)}) are analyzing different aspects simultaneously\n"
            coordination_context += f"- Use the EXACT time period and dates specified below to ensure consistency with other agents\n"
            if comparison_mode:
                coordination_context += f"- This is a COMPARISON analysis - your results will be compared with other agents' findings\n"
        
        # Build the enhanced message
        enhanced_message = f"""ORCHESTRATOR INSTRUCTION:

You are the {agent_name.replace('_', ' ').title()} agent, specializing in {agent_role}.

ORCHESTRATOR'S INTENT:
{intent}

YOUR SPECIFIC ROLE:
- Focus on {agent_role} for the Quiz advertiser
- Use the normalized parameters provided below to ensure consistency
- Provide clear, actionable insights relevant to your domain
{coordination_context}
NORMALIZED PARAMETERS (USE THESE EXACTLY):
- Time Period: {time_period}
- Start Date: {start_date if start_date else 'Not specified - use your domain knowledge'}
- End Date: {end_date if end_date else 'Not specified - use your domain knowledge'}
{time_context}

USER'S ORIGINAL QUERY:
{user_query}

IMPORTANT:
- Use the dates/time period specified above, not your interpretation of the user's query
- If dates are provided, use them exactly as specified
- Remember: There is NO data for today's date - always exclude today from queries
- Provide a focused analysis on {agent_role} - the orchestrator will coordinate with other agents for the complete picture"""
        
        return enhanced_message

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph StateGraph."""
        workflow = StateGraph(OrchestratorState)

        # Add nodes
        workflow.add_node("orchestrator_analysis", self._orchestrator_analysis_node)
        workflow.add_node("gate", self._gate_node)
        workflow.add_node("invoke_agents", self._invoke_agents_node)
        workflow.add_node("orchestrator_review", self._orchestrator_review_node)
        workflow.add_node("requery_agents", self._requery_agents_node)
        workflow.add_node("orchestrator_coordination", self._orchestrator_coordination_node)
        workflow.add_node("validation", self._validation_node)
        workflow.add_node("generate_response", self._generate_response_node)

        # Set entry point
        workflow.set_entry_point("orchestrator_analysis")

        # Conditional: orchestrator_analysis can go to gate (normal) or generate_response (clarification needed)
        workflow.add_conditional_edges(
            "orchestrator_analysis",
            self._orchestrator_analysis_decision,
            {
                "clarify": "generate_response",  # Skip to response for clarification
                "proceed": "gate"  # Normal flow
            }
        )

        # Conditional: gate validates or blocks
        workflow.add_conditional_edges(
            "gate",
            self._gate_decision,
            {
                "proceed": "invoke_agents",
                "block": "generate_response"  # Generate error response
            }
        )

        workflow.add_edge("invoke_agents", "orchestrator_review")

        # Conditional: orchestrator_review can loop back (requery) or proceed
        workflow.add_conditional_edges(
            "orchestrator_review",
            self._review_decision,
            {
                "requery": "requery_agents",  # Loop back to re-query agents
                "proceed": "orchestrator_coordination"  # Proceed to coordination
            }
        )

        workflow.add_edge("requery_agents", "orchestrator_review")  # Loop back to review

        # Conditional: early exit or continue
        workflow.add_conditional_edges(
            "orchestrator_coordination",
            self._early_exit_decision,
            {
                "exit": "generate_response",
                "continue": "validation"
            }
        )

        workflow.add_edge("validation", "generate_response")
        workflow.add_edge("generate_response", END)

        return workflow.compile()

    def _orchestrator_analysis_decision(self, state: OrchestratorState) -> str:
        """Decision: proceed to gate or skip to clarification response?"""
        if state.get("clarification_needed", False):
            logger.info("Orchestrator analysis: clarification needed, skipping to response")
            return "clarify"
        else:
            logger.info("Orchestrator analysis: proceeding to gate")
            return "proceed"

    async def _orchestrator_analysis_node(self, state: OrchestratorState) -> Dict[str, Any]:
        """
        Orchestrator analysis: Understand query, decide agents, extract parameters.
        
        This node replaces routing and adds parameter extraction/coordination.
        It can ask for clarification if the query is unclear.
        """
        from datetime import datetime, timedelta
        from langchain_core.messages import SystemMessage, HumanMessage
        
        query = state["query"]
        session_id = state.get("session_id")

        logger.info("Orchestrator analyzing query", query=query[:50])

        # Emit progress: started
        await self._emit_progress("orchestrator_analysis", "started", {
            "message": "Analyzing query and creating coordinated strategy..."
        })

        # Fetch recent conversation history for context
        conversation_history = []
        if session_id:
            try:
                messages = await session_manager.get_messages(session_id, limit=10)
                if len(messages) > 1:
                    filtered_messages = [
                        msg for msg in messages
                        if msg.content != query
                    ]
                    conversation_history = [
                        {"role": msg.role, "content": msg.content}
                        for msg in filtered_messages
                    ]
                logger.info("Fetched conversation history", message_count=len(conversation_history))
            except Exception as e:
                logger.warning("Failed to fetch conversation history", error=str(e))

        # Build context section
        context_section = ""
        if conversation_history:
            recent_messages = conversation_history[-6:]
            context_lines = []
            for msg in recent_messages:
                role = "User" if msg["role"] == "user" else "Assistant"
                content = msg["content"][:300] + "..." if len(msg["content"]) > 300 else msg["content"]
                context_lines.append(f"{role}: {content}")
            context_section = f"\nCONVERSATION HISTORY:\n{chr(10).join(context_lines)}\n"

        # Build agent descriptions
        agent_list = []
        for agent_name, agent in self.specialist_agents.items():
            agent_list.append(f"- **{agent_name}**: {agent.description if hasattr(agent, 'description') else agent_name}")

        agents_description = "\n".join(agent_list)
        current_date = datetime.now()
        current_date_str = current_date.strftime("%B %Y")
        current_year = current_date.year

        # Build orchestrator analysis prompt
        analysis_prompt = f"""You are the Orchestrator Coordinator for a DV360 analysis system. Your job is to:
1. Understand the user's query intent
2. Decide which specialist agents should handle it
3. Extract and normalize query parameters (time periods, dates, filters)
4. Create a coordinated strategy so all agents use consistent parameters

{context_section}

IMPORTANT: The current date is {current_date_str} (year {current_year}). All date references should be interpreted relative to {current_year} unless explicitly stated otherwise.

Available agents:
{agents_description}

User query: "{query}"

CRITICAL - DATE EXCLUSION RULE:
- There is NO data for today's date - data is only available up to YESTERDAY
- When users ask for "last N days", query N+1 days back to yesterday
- Example: "last 7 days" = DATE >= DATEADD(day, -8, CURRENT_DATE()) AND DATE < CURRENT_DATE()
- Never use DATE >= CURRENT_DATE() or DATE = CURRENT_DATE()

Your task:
1. Analyze the query to understand intent
2. Select appropriate agent(s) - can be multiple if query requires comparison
3. Extract time period parameters:
   - "recently" → "last_7_days"
   - "last week" → calculate last full week (Sunday-Saturday)
   - "last N days" → "last_N_days" (remember: N+1 days back to yesterday)
   - "this month" → current month (excluding today)
   - Specific dates → extract start_date and end_date
4. Normalize all parameters to ensure consistency across agents

Respond in this exact format:

AGENTS: agent_name_1, agent_name_2 (or NONE if query is truly unclear and you cannot proceed)
INTENT: Brief description of what user wants to know
TIME_PERIOD: normalized_time_period (e.g., "last_7_days", "last_30_days", "current_month", "custom")
START_DATE: YYYY-MM-DD (if specific dates, otherwise leave empty)
END_DATE: YYYY-MM-DD (if specific dates, otherwise leave empty)
COMPARISON_MODE: true/false (true if comparing multiple agents/data sources)
CLARIFICATION: ONLY include this line if the query is truly unclear/ambiguous and you CANNOT proceed. Do NOT include informational notes or warnings here.

CRITICAL: 
- If you can understand the query and select an agent, DO NOT include CLARIFICATION
- CLARIFICATION should ONLY be used when the query is so vague/ambiguous that you cannot determine what the user wants
- Examples that need clarification: "hello", "help", "show me data" (no context), "what's happening" (too vague)
- Examples that DO NOT need clarification: "Quiz performance last week", "budget status", "show me ROAS" (even if ROAS might not be available, proceed with the query)

Examples:
- "recently" → TIME_PERIOD: last_7_days, START_DATE: (empty), END_DATE: (empty) [NO CLARIFICATION needed]
- "last week" → TIME_PERIOD: last_full_week, START_DATE: 2026-01-10, END_DATE: 2026-01-17 [NO CLARIFICATION needed]
- "Jan 4-17" → TIME_PERIOD: custom, START_DATE: 2026-01-04, END_DATE: 2026-01-17 [NO CLARIFICATION needed]
- "this month" → TIME_PERIOD: current_month, START_DATE: 2026-01-01, END_DATE: (yesterday) [NO CLARIFICATION needed]
- "show me ROAS" → AGENTS: performance_diagnosis, proceed even if ROAS might not be available [NO CLARIFICATION needed]

Only include CLARIFICATION if:
- Query is so vague you cannot determine intent (e.g., "hello", "help", "data")
- Query is completely ambiguous (e.g., "show me something")
- You truly cannot proceed without more information

Your analysis:"""

        try:
            messages = [
                SystemMessage(content=self.get_system_prompt()),
                HumanMessage(content=analysis_prompt)
            ]

            response = self.llm.invoke(messages)
            response_text = response.content.strip()

            logger.info("Orchestrator analysis response", response_preview=response_text[:200])

            # Parse response
            selected_agents = []
            intent = ""
            time_period = ""
            start_date = ""
            end_date = ""
            comparison_mode = False
            clarification_message = ""

            for line in response_text.split('\n'):
                line = line.strip()
                if line.startswith("AGENTS:"):
                    agents_part = line.replace("AGENTS:", "").strip()
                    if agents_part.upper() != "NONE":
                        selected_agents = [a.strip() for a in agents_part.split(',') if a.strip()]
                elif line.startswith("INTENT:"):
                    intent = line.replace("INTENT:", "").strip()
                elif line.startswith("TIME_PERIOD:"):
                    time_period = line.replace("TIME_PERIOD:", "").strip()
                elif line.startswith("START_DATE:"):
                    start_date = line.replace("START_DATE:", "").strip()
                elif line.startswith("END_DATE:"):
                    end_date = line.replace("END_DATE:", "").strip()
                elif line.startswith("COMPARISON_MODE:"):
                    comparison_mode = line.replace("COMPARISON_MODE:", "").strip().lower() == "true"
                elif line.startswith("CLARIFICATION:"):
                    clarification_message = line.replace("CLARIFICATION:", "").strip()

            # Check if clarification is needed
            # Only clarify if NO agents were selected (query is truly unclear)
            # If agents were selected, proceed even if clarification message exists (it's just informational)
            needs_clarification = not selected_agents
            
            if needs_clarification:
                logger.info("Orchestrator analysis: clarification needed - no agents selected", query=query[:50])
                
                await self._emit_progress("orchestrator_analysis", "completed", {
                    "message": "Query unclear - requesting clarification",
                    "clarification_needed": True
                })

                return {
                    "strategy": {},
                    "analysis_result": {
                        "intent": intent,
                        "selected_agents": [],
                        "confidence": 0.0
                    },
                    "selected_agents": [],
                    "normalized_params": {},
                    "clarification_needed": True,
                    "clarification_message": clarification_message or "Could you please clarify what information you need? For example: 'Show me Quiz performance for last week' or 'What's the budget status for January?'",
                    "conversation_history": conversation_history,
                    "reasoning_steps": [
                        "Orchestrator analysis: Query unclear, requesting clarification"
                    ]
                }
            
            # If agents were selected but clarification message exists, log it as informational only
            if clarification_message and selected_agents:
                logger.info(
                    "Orchestrator analysis: agents selected, clarification message ignored (informational only)",
                    agents=selected_agents,
                    clarification_note=clarification_message[:100]
                )

            # Calculate dates if needed
            normalized_params = {
                "time_period": time_period,
                "comparison_mode": comparison_mode
            }

            if start_date:
                normalized_params["start_date"] = start_date
            if end_date:
                normalized_params["end_date"] = end_date

            # Calculate dates for relative time periods
            if time_period == "last_7_days":
                end_date_obj = current_date - timedelta(days=1)  # Yesterday
                start_date_obj = end_date_obj - timedelta(days=7)  # 8 days back
                normalized_params["start_date"] = start_date_obj.strftime("%Y-%m-%d")
                normalized_params["end_date"] = end_date_obj.strftime("%Y-%m-%d")
            elif time_period == "last_30_days":
                end_date_obj = current_date - timedelta(days=1)
                start_date_obj = end_date_obj - timedelta(days=30)
                normalized_params["start_date"] = start_date_obj.strftime("%Y-%m-%d")
                normalized_params["end_date"] = end_date_obj.strftime("%Y-%m-%d")
            elif time_period == "current_month":
                normalized_params["start_date"] = f"{current_year}-{current_date.month:02d}-01"
                normalized_params["end_date"] = (current_date - timedelta(days=1)).strftime("%Y-%m-%d")

            # Create strategy
            strategy = {
                "selected_agents": selected_agents,
                "normalized_params": normalized_params,
                "intent": intent,
                "comparison_mode": comparison_mode
            }

            # Emit progress: completed
            await self._emit_progress("orchestrator_analysis", "completed", {
                "message": f"Strategy created: {', '.join(selected_agents)}",
                "agents": selected_agents,
                "time_period": time_period
            })

            return {
                "strategy": strategy,
                "analysis_result": {
                    "intent": intent,
                    "selected_agents": selected_agents,
                    "confidence": 0.9
                },
                "selected_agents": selected_agents,
                "normalized_params": normalized_params,
                "clarification_needed": False,
                "conversation_history": conversation_history,
                "reasoning_steps": [
                    f"Orchestrator analysis: Selected {', '.join(selected_agents)} "
                    f"with time_period={time_period}, comparison_mode={comparison_mode}"
                ]
            }

        except Exception as e:
            logger.error("Orchestrator analysis failed", error=str(e))
            return {
                "strategy": {},
                "analysis_result": {"error": str(e)},
                "selected_agents": [],
                "normalized_params": {},
                "clarification_needed": True,
                "clarification_message": "I encountered an error analyzing your query. Could you please rephrase it?",
                "reasoning_steps": [f"Orchestrator analysis failed: {str(e)}"]
            }

    async def _gate_node(self, state: OrchestratorState) -> Dict[str, Any]:
        """Validate orchestrator's strategy."""
        # Skip gate validation if clarification is needed
        if state.get("clarification_needed", False):
            logger.info("Gate skipped - clarification needed")
            return {
                "gate_result": {
                    "valid": False,
                    "reason": "Clarification needed",
                    "approved_agents": [],
                    "warnings": []
                },
                "reasoning_steps": ["Gate: Skipped - clarification needed"]
            }
        
        query = state["query"]
        selected_agents = state["selected_agents"]
        strategy = state.get("strategy", {})
        analysis_result = state.get("analysis_result", {})
        confidence = analysis_result.get("confidence", 0.8)

        logger.info("Gate validation", selected_agents=selected_agents)

        # Emit progress: started
        await self._emit_progress("gate", "started", {"message": "Validating request..."})

        # Use gate node (validate orchestrator's strategy)
        gate_result = gate_node.validate(
            query=query,
            selected_agents=selected_agents,
            routing_confidence=confidence,  # Use analysis confidence
            user_id=state["user_id"]
        )

        approved = gate_result.get('approved_agents', [])
        warnings = gate_result.get('warnings', [])

        # Emit progress: completed
        await self._emit_progress("gate", "completed", {
            "message": f"Validated: {len(approved)} agent(s) approved" if gate_result.get("valid") else "Request blocked",
            "approved_agents": approved,
            "warnings": warnings
        })

        return {
            "gate_result": gate_result,
            "reasoning_steps": [
                f"Gate: approved {len(approved)} agents, {len(warnings)} warnings"
            ]
        }

    def _gate_decision(self, state: OrchestratorState) -> str:
        """Decision: proceed or block?"""
        gate_result = state.get("gate_result", {})
        valid = gate_result.get("valid", False)

        if valid:
            logger.info("Gate decision: proceed")
            return "proceed"
        else:
            logger.warning("Gate decision: block", reason=gate_result.get("reason"))
            return "block"

    async def _invoke_agents_node(self, state: OrchestratorState) -> Dict[str, Any]:
        """Invoke approved specialist agents."""
        gate_result = state.get("gate_result", {})
        approved_agents = gate_result.get("approved_agents", [])
        query = state["query"]
        session_id = state.get("session_id")
        user_id = state["user_id"]

        logger.info("Invoking agents", agents=approved_agents)

        # Emit progress: started
        await self._emit_progress("invoke_agents", "started", {
            "message": f"Running {len(approved_agents)} agent(s)...",
            "agents": approved_agents
        })

        # Fetch conversation history for context (excluding current query)
        conversation_history = []
        if session_id:
            try:
                messages = await session_manager.get_messages(session_id, limit=10)
                # Only include history if there are previous messages (not just the current one)
                # Filter out any messages that match the current query (it might be saved already)
                if len(messages) > 1:  # More than just the current message
                    # Exclude messages that match the current query
                    filtered_messages = [
                        msg for msg in messages
                        if msg.content != query  # Exclude current query if it's already saved
                    ]
                    conversation_history = [
                        {"role": msg.role, "content": msg.content}
                        for msg in filtered_messages
                    ]
                # If only 1 message exists, it's likely the current query, so no history
                logger.info("Fetched conversation history for agents", message_count=len(conversation_history), total_messages=len(messages))
            except Exception as e:
                logger.warning("Failed to fetch conversation history for agents", error=str(e))

        agent_results = {}
        agent_errors = {}

        # Create agent input with orchestrator's strategy and normalized parameters
        strategy = state.get("strategy", {})
        normalized_params = state.get("normalized_params", {})
        
        # Emit progress: all agents starting
        await self._emit_progress("invoke_agents", "running", {
            "message": f"Running {len(approved_agents)} agent(s) in parallel...",
            "agents": approved_agents
        })

        async def invoke_single_agent(agent_name: str):
            """Invoke a single agent and return result or error."""
            agent = self.specialist_agents.get(agent_name)
            if not agent:
                logger.warning(f"Agent {agent_name} not found")
                return agent_name, None, "Agent not found"

            try:
                # Emit progress: running this agent
                await self._emit_progress("invoke_agents", "running", {
                    "message": f"Running {agent_name}...",
                    "current_agent": agent_name
                })

                # Build enhanced message with orchestrator instructions
                enhanced_message = self._build_agent_message(
                    agent_name=agent_name,
                    user_query=query,
                    strategy=strategy,
                    normalized_params=normalized_params
                )
                
                agent_input = AgentInput(
                    message=enhanced_message,
                    session_id=session_id,
                    user_id=user_id,
                    context={
                        "conversation_history": conversation_history,
                        "strategy": strategy,  # Full strategy from orchestrator
                        "normalized_params": normalized_params,  # Normalized parameters for consistency
                        "comparison_mode": strategy.get("comparison_mode", False),
                        "orchestrator_intent": strategy.get("intent", ""),  # What the orchestrator is trying to achieve
                        "selected_agents": strategy.get("selected_agents", [])  # All agents in this analysis
                    }
                )

                # Invoke agent (this is async and will run in parallel with others)
                agent_output = await agent.invoke(agent_input)

                logger.info(f"Agent {agent_name} completed", confidence=agent_output.confidence)

                # Emit progress: agent completed
                await self._emit_progress("invoke_agents", "running", {
                    "message": f"Completed {agent_name}",
                    "completed_agent": agent_name,
                    "confidence": agent_output.confidence
                })

                return agent_name, agent_output, None

            except Exception as e:
                logger.error(f"Agent {agent_name} failed", error_message=str(e))
                return agent_name, None, str(e)

        # Run all agents in parallel using asyncio.gather
        tasks = [invoke_single_agent(agent_name) for agent_name in approved_agents]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for result in results:
            if isinstance(result, Exception):
                # Handle unexpected exceptions
                logger.error("Unexpected exception in agent invocation", error=str(result))
                continue
            
            agent_name, agent_output, error = result
            if error:
                agent_errors[agent_name] = error
            elif agent_output:
                agent_results[agent_name] = agent_output

        # Emit progress: all agents completed
        await self._emit_progress("invoke_agents", "completed", {
            "message": f"All {len(agent_results)} agent(s) completed",
            "agents_invoked": list(agent_results.keys()),
            "errors": list(agent_errors.keys()) if agent_errors else []
        })

        return {
            "agent_results": agent_results,
            "agent_errors": agent_errors,
            "reasoning_steps": [
                f"Invoked {len(agent_results)} agents successfully, "
                f"{len(agent_errors)} failed"
            ]
        }

    async def _orchestrator_review_node(self, state: OrchestratorState) -> Dict[str, Any]:
        """
        Review agent results for consistency.
        
        Checks if agents used consistent time periods and parameters.
        Can trigger re-query if mismatches detected.
        """
        from langchain_core.messages import SystemMessage, HumanMessage
        
        agent_results = state["agent_results"]
        normalized_params = state.get("normalized_params", {})
        strategy = state.get("strategy", {})
        requery_count = state.get("requery_count", 0)
        max_requeries = state.get("max_requeries", 2)
        
        logger.info("Orchestrator reviewing agent results", agents=list(agent_results.keys()))
        
        # Emit progress: started
        await self._emit_progress("orchestrator_review", "started", {
            "message": "Reviewing agent results for consistency..."
        })
        
        # If max retries reached, proceed anyway
        if requery_count >= max_requeries:
            logger.warning("Max retries reached, proceeding with current results")
            return {
                "review_result": {
                    "consistent": False,
                    "requery_needed": False,
                    "max_retries_reached": True,
                    "mismatches": []
                },
                "reasoning_steps": ["Review: Max retries reached, proceeding"]
            }
        
        # Extract time periods from agent responses
        expected_time_period = normalized_params.get("time_period", "")
        expected_start_date = normalized_params.get("start_date", "")
        expected_end_date = normalized_params.get("end_date", "")
        
        agent_time_periods = {}
        mismatches = []
        
        # Use LLM to extract time periods from agent responses
        review_prompt = f"""You are reviewing agent results for consistency. Extract the time periods used by each agent.

Expected parameters from orchestrator:
- Time Period: {expected_time_period}
- Start Date: {expected_start_date}
- End Date: {expected_end_date}

Agent Results:
"""
        
        for agent_name, output in agent_results.items():
            response_preview = output.response[:500] if output.response else ""
            review_prompt += f"\n{agent_name}:\n{response_preview}\n"
        
        review_prompt += """
Extract the time period used by each agent from their responses.

Respond in format:
AGENT: agent_name
TIME_PERIOD: extracted_time_period
START_DATE: YYYY-MM-DD (if mentioned)
END_DATE: YYYY-MM-DD (if mentioned)
MATCHES: true/false (does it match expected?)

Your review:"""
        
        try:
            messages = [
                SystemMessage(content="You are a consistency reviewer for agent results."),
                HumanMessage(content=review_prompt)
            ]
            
            response = self.llm.invoke(messages)
            response_text = response.content.strip()
            
            # Parse response to extract time periods
            current_agent = None
            for line in response_text.split('\n'):
                line = line.strip()
                if line.startswith("AGENT:"):
                    current_agent = line.replace("AGENT:", "").strip()
                elif line.startswith("TIME_PERIOD:") and current_agent:
                    agent_time_periods[current_agent] = line.replace("TIME_PERIOD:", "").strip()
                elif line.startswith("MATCHES:") and current_agent:
                    matches = line.replace("MATCHES:", "").strip().lower() == "true"
                    if not matches:
                        mismatches.append({
                            "agent": current_agent,
                            "expected": expected_time_period,
                            "actual": agent_time_periods.get(current_agent, "unknown")
                        })
            
            # Determine if re-query is needed
            consistent = len(mismatches) == 0
            requery_needed = not consistent and requery_count < max_requeries
            
            logger.info(
                "Review complete",
                consistent=consistent,
                mismatches=len(mismatches),
                requery_needed=requery_needed
            )
            
            # Emit progress: completed
            await self._emit_progress("orchestrator_review", "completed", {
                "message": f"Review complete: {'consistent' if consistent else 'mismatches detected'}",
                "consistent": consistent,
                "mismatches": len(mismatches)
            })
            
            return {
                "review_result": {
                    "consistent": consistent,
                    "requery_needed": requery_needed,
                    "mismatches": mismatches,
                    "agent_time_periods": agent_time_periods
                },
                "agent_time_periods": agent_time_periods,
                "reasoning_steps": [
                    f"Review: {'Consistent' if consistent else f'{len(mismatches)} mismatch(es) detected'}"
                ]
            }
            
        except Exception as e:
            logger.error("Review failed", error=str(e))
            # On error, proceed (don't block)
            return {
                "review_result": {
                    "consistent": True,  # Assume consistent on error
                    "requery_needed": False,
                    "mismatches": [],
                    "error": str(e)
                },
                "agent_time_periods": {},
                "reasoning_steps": [f"Review failed: {str(e)}, proceeding"]
            }
    
    def _review_decision(self, state: OrchestratorState) -> str:
        """Decision: requery agents or proceed?"""
        review_result = state.get("review_result", {})
        requery_needed = review_result.get("requery_needed", False)
        
        if requery_needed:
            logger.info("Review decision: re-query needed")
            return "requery"
        else:
            logger.info("Review decision: proceeding to coordination")
            return "proceed"
    
    async def _requery_agents_node(self, state: OrchestratorState) -> Dict[str, Any]:
        """
        Re-query agents with normalized parameters from orchestrator strategy.
        
        This node re-invokes agents with explicit parameters to ensure consistency.
        """
        gate_result = state.get("gate_result", {})
        approved_agents = gate_result.get("approved_agents", [])
        query = state["query"]
        session_id = state.get("session_id")
        user_id = state["user_id"]
        normalized_params = state.get("normalized_params", {})
        strategy = state.get("strategy", {})
        requery_count = state.get("requery_count", 0)
        
        logger.info("Re-querying agents with normalized parameters", agents=approved_agents, retry=requery_count + 1)
        
        # Emit progress: started
        await self._emit_progress("requery_agents", "started", {
            "message": f"Re-querying agents with normalized parameters (retry {requery_count + 1})..."
        })
        
        # Fetch conversation history
        conversation_history = state.get("conversation_history", [])
        
        agent_results = {}
        agent_errors = {}
        
        for agent_name in approved_agents:
            agent = self.specialist_agents.get(agent_name)
            if not agent:
                continue
            
            try:
                # Create agent input with explicit normalized parameters
                # Add instruction to use these parameters
                enhanced_query = query
                if normalized_params.get("start_date") and normalized_params.get("end_date"):
                    enhanced_query = f"{query} (Use dates: {normalized_params['start_date']} to {normalized_params['end_date']})"
                elif normalized_params.get("time_period"):
                    enhanced_query = f"{query} (Use time period: {normalized_params['time_period']})"
                
                agent_input = AgentInput(
                    message=enhanced_query,
                    session_id=session_id,
                    user_id=user_id,
                    context={
                        "conversation_history": conversation_history,
                        "strategy": strategy,
                        "normalized_params": normalized_params,
                        "comparison_mode": strategy.get("comparison_mode", False),
                        "requery": True,  # Flag that this is a re-query
                        "requery_count": requery_count + 1
                    }
                )
                
                agent_output = await agent.invoke(agent_input)
                agent_results[agent_name] = agent_output
                
                logger.info(f"Re-queried agent {agent_name} completed", confidence=agent_output.confidence)
                
            except Exception as e:
                logger.error(f"Re-query agent {agent_name} failed", error_message=str(e))
                agent_errors[agent_name] = str(e)
        
        # Emit progress: completed
        await self._emit_progress("requery_agents", "completed", {
            "message": f"Re-queried {len(agent_results)} agent(s)",
            "agents_invoked": list(agent_results.keys())
        })
        
        return {
            "agent_results": agent_results,  # Update agent results
            "agent_errors": agent_errors,
            "requery_count": requery_count + 1,
            "reasoning_steps": [
                f"Re-queried {len(agent_results)} agents with normalized parameters (retry {requery_count + 1})"
            ]
        }
    
    async def _orchestrator_coordination_node(self, state: OrchestratorState) -> Dict[str, Any]:
        """
        Coordinate diagnosis and recommendations.
        
        This replaces the old diagnosis_recommendation_node but now receives
        validated, consistent agent results from the review node.
        """
        agent_results = state["agent_results"]
        query = state["query"]
        gate_result = state.get("gate_result", {})
        approved_agents = gate_result.get("approved_agents", [])
        review_result = state.get("review_result", {})
        
        logger.info("Orchestrator coordinating diagnosis and recommendations")
        
        # Emit progress: started
        await self._emit_progress("orchestrator_coordination", "started", {
            "message": "Coordinating diagnosis and recommendations..."
        })
        
        # Skip coordination for follow-up queries
        follow_up_phrases = ["yes i do", "yes", "no", "that one", "the first", "the second", "re run", "point 1"]
        is_follow_up = any(phrase in query.lower() for phrase in follow_up_phrases)
        
        if is_follow_up and len(approved_agents) == 1:
            logger.info("Skipping coordination for follow-up query")
            agent_name = approved_agents[0]
            agent_output = agent_results.get(agent_name)
            
            diagnosis = {
                "summary": agent_output.response if agent_output else "Query processed successfully",
                "severity": "low",
                "root_causes": [],
                "correlations": [],
                "issues": []
            }
            
            return {
                "coordination_result": {
                    "diagnosis": diagnosis,
                    "recommendations": []
                },
                "diagnosis": diagnosis,
                "recommendations": [],
                "recommendation_confidence": 0.0,
                "correlations": [],
                "severity_assessment": "low",
                "reasoning_steps": ["Coordination skipped: Follow-up query"]
            }
        
        # Skip coordination for single-agent informational queries
        if len(approved_agents) == 1 and self._is_informational_query(query):
            logger.info("Skipping coordination for single-agent informational query")
            agent_name = approved_agents[0]
            agent_output = agent_results.get(agent_name)
            
            diagnosis = {
                "summary": agent_output.response if agent_output else "Query processed successfully",
                "severity": "low",
                "root_causes": [],
                "correlations": [],
                "issues": []
            }
            
            return {
                "coordination_result": {
                    "diagnosis": diagnosis,
                    "recommendations": []
                },
                "diagnosis": diagnosis,
                "recommendations": [],
                "recommendation_confidence": 0.0,
                "correlations": [],
                "severity_assessment": "low",
                "reasoning_steps": ["Coordination skipped: Single-agent informational query"]
            }
        
        # Use diagnosis_recommendation_agent for multi-agent or complex queries
        conversation_history = state.get("conversation_history", [])
        gate_warnings = gate_result.get("warnings", [])
        strategy = state.get("strategy", {})
        normalized_params = state.get("normalized_params", {})
        agent_time_periods = state.get("agent_time_periods", {})
        requery_count = state.get("requery_count", 0)
        
        # Build review context to pass to diagnosis agent
        review_context = {
            "consistent": review_result.get("consistent", True),
            "mismatches": review_result.get("mismatches", []),
            "requery_count": requery_count,
            "expected_time_period": normalized_params.get("time_period", ""),
            "expected_dates": {
                "start_date": normalized_params.get("start_date", ""),
                "end_date": normalized_params.get("end_date", "")
            },
            "actual_time_periods": agent_time_periods,
            "comparison_mode": strategy.get("comparison_mode", False)
        }
        
        # Log review findings for coordination
        if not review_result.get("consistent", True):
            logger.info(
                "Coordination with inconsistent results",
                mismatches=len(review_result.get("mismatches", [])),
                requery_count=requery_count
            )
        
        result = await diagnosis_recommendation_agent.analyze_and_recommend(
            agent_results,
            query,
            conversation_history=conversation_history,
            gate_warnings=gate_warnings,
            review_context=review_context  # Pass review findings
        )
        
        diagnosis = result.get("diagnosis", {})
        recommendations = result.get("recommendations", [])
        confidence = result.get("confidence", 0.8)
        
        # Emit progress: completed
        await self._emit_progress("orchestrator_coordination", "completed", {
            "message": f"Coordination complete: {len(recommendations)} recommendation(s)",
            "recommendations_count": len(recommendations),
            "severity": diagnosis.get("severity")
        })
        
        return {
            "coordination_result": result,
            "diagnosis": diagnosis,
            "recommendations": recommendations,
            "recommendation_confidence": confidence,
            "correlations": result.get("correlations", []),
            "severity_assessment": result.get("severity_assessment", "medium"),
            "reasoning_steps": [
                f"Coordination: {len(diagnosis.get('root_causes', []))} root causes, "
                f"{len(recommendations)} recommendations"
            ]
        }

    def _is_informational_query(self, query: str) -> bool:
        """
        Check if query is informational (asking for information) vs action-oriented.
        
        Informational queries: "what is", "how is", "show me", "tell me about", "explain"
        Action-oriented queries: "optimize", "fix", "improve", "why is", "what's wrong"
        """
        query_lower = query.lower()
        informational_keywords = [
            "what is", "what are", "what was", "what will",
            "how is", "how are", "how was", "how will",
            "show me", "tell me", "explain", "describe",
            "list", "give me", "provide"
        ]
        
        action_keywords = [
            "optimize", "fix", "improve", "why is", "why are",
            "what's wrong", "what went wrong", "issue", "problem",
            "recommend", "suggest", "should", "need to"
        ]
        
        # Check for action keywords first (higher priority)
        if any(keyword in query_lower for keyword in action_keywords):
            return False
        
        # Check for informational keywords
        return any(keyword in query_lower for keyword in informational_keywords)

    def _early_exit_decision(self, state: OrchestratorState) -> str:
        """Decision: exit early or continue to validation?"""
        diagnosis = state["diagnosis"]
        recommendations = state.get("recommendations", [])
        agent_results = state["agent_results"]
        query = state["query"]

        # Check if we should exit early
        exit_decision = early_exit_node.should_exit_early(diagnosis, agent_results, query)

        should_exit = exit_decision.get("exit", False)
        
        # Also exit early if no recommendations were generated (informational query)
        if not should_exit and len(recommendations) == 0:
            # No recommendations means it was likely informational - exit early
            logger.info("Early exit triggered - no recommendations generated")
            state["final_response"] = diagnosis.get("summary", "") or exit_decision.get("final_response", "")
            state["should_exit_early"] = True
            state["early_exit_reason"] = "Informational query - no recommendations needed"
            return "exit"

        if should_exit:
            logger.info("Early exit triggered", reason=exit_decision.get("reason"))
            # Store early exit response
            state["final_response"] = exit_decision.get("final_response") or diagnosis.get("summary", "")
            state["should_exit_early"] = True
            state["early_exit_reason"] = exit_decision.get("reason")
            return "exit"
        else:
            logger.info("Continuing to validation")
            return "continue"

    async def _validation_node(self, state: OrchestratorState) -> Dict[str, Any]:
        """Validate recommendations."""
        recommendations = state["recommendations"]
        diagnosis = state["diagnosis"]
        agent_results = state["agent_results"]

        logger.info("Validating recommendations", count=len(recommendations))

        # Emit progress: started
        await self._emit_progress("validation", "started", {"message": "Validating recommendations..."})

        # Use validation agent
        validation_result = validation_agent.validate_recommendations(
            recommendations, diagnosis, agent_results
        )

        validated = validation_result.get("validated_recommendations", [])
        warnings = validation_result.get("warnings", [])

        # Emit progress: completed
        await self._emit_progress("validation", "completed", {
            "message": f"Validated {len(validated)} recommendation(s)",
            "validated_count": len(validated),
            "warnings_count": len(warnings)
        })

        return {
            "validation_result": validation_result,
            "validated_recommendations": validated,
            "validation_warnings": warnings,
            "reasoning_steps": [
                f"Validation: {len(validated)} "
                f"recommendations validated, {len(warnings)} warnings"
            ]
        }

    async def _generate_response_node(self, state: OrchestratorState) -> Dict[str, Any]:
        """Generate final response."""
        # Emit progress: started
        await self._emit_progress("generate_response", "started", {"message": "Formatting response..."})

        # Check if clarification is needed
        if state.get("clarification_needed", False):
            final_response = state.get("clarification_message", "Could you please clarify your question?")
            confidence = 0.0
        # Check if early exit
        elif state.get("should_exit_early"):
            final_response = state.get("final_response", "")
            confidence = 0.8
        else:
            # Check if gate blocked
            gate_result = state.get("gate_result", {})
            if not gate_result.get("valid", True):
                final_response = f"Unable to process query: {gate_result.get('reason', 'Invalid request')}"
                confidence = 0.0
            else:
                # Normal response with recommendations
                final_response = self._build_response(state)
                confidence = state.get("recommendation_confidence", 0.8)

        logger.info("Generated final response", length=len(final_response), confidence=confidence)

        # Emit progress: completed
        await self._emit_progress("generate_response", "completed", {
            "message": "Response ready",
            "confidence": confidence
        })

        return {
            "final_response": final_response,
            "confidence": confidence,
            "reasoning_steps": ["Generated final response"]
        }

    def _build_response(self, state: OrchestratorState) -> str:
        """Build final response from state."""
        parts = []

        # Header
        query = state["query"]
        parts.append(f"# Analysis Results\n")
        parts.append(f"**Query**: {query}\n")

        # Check if we have good recommendations - prioritize them over diagnosis
        validated_recs = state.get("validated_recommendations", [])
        diagnosis = state.get("diagnosis", {})
        
        # If we have recommendations, prioritize them and only show diagnosis if it's meaningful
        if validated_recs and len(validated_recs) > 0:
            # Show recommendations first (they're the actionable output)
            parts.append(f"\n## Recommendations")
            for i, rec in enumerate(validated_recs, 1):
                priority = rec.get("priority", "medium").upper()
                action = rec.get("action", "N/A")
                reason = rec.get("reason", "N/A")
                expected_impact = rec.get("expected_impact", "")
                
                parts.append(f"\n### {i}. [{priority}] {action}")
                parts.append(f"**Why**: {reason}")
                if expected_impact:
                    parts.append(f"**Expected Impact**: {expected_impact}")
            
            # Only show diagnosis if it's meaningful (not from a follow-up query)
            # Check if diagnosis summary is actually useful (not just analyzing the follow-up)
            diagnosis_summary = diagnosis.get("summary", "")
            if diagnosis and diagnosis_summary and len(diagnosis_summary) > 50:
                # Check if diagnosis is analyzing a follow-up query (like "yes I do")
                follow_up_phrases = ["yes i do", "yes", "no", "that one", "the first", "the second"]
                is_follow_up = any(phrase in query.lower() for phrase in follow_up_phrases)
                
                # Only include diagnosis if it's not analyzing a follow-up
                if not is_follow_up:
                    parts.append(f"\n## Diagnosis")
                    parts.append(f"**Severity**: {diagnosis.get('severity', 'N/A').upper()}")
                    if diagnosis_summary:
                        parts.append(f"\n{diagnosis_summary}\n")
                    
                    if diagnosis.get("root_causes"):
                        parts.append(f"\n**Root Causes**:")
                        for cause in diagnosis["root_causes"]:
                            parts.append(f"- {cause}")
        else:
            # No recommendations - show diagnosis as primary content
            if diagnosis:
                parts.append(f"\n## Diagnosis")
                parts.append(f"**Severity**: {diagnosis.get('severity', 'N/A').upper()}")
                if diagnosis.get("summary"):
                    parts.append(f"\n{diagnosis['summary']}\n")

                if diagnosis.get("root_causes"):
                    parts.append(f"\n**Root Causes**:")
                    for cause in diagnosis["root_causes"]:
                        parts.append(f"- {cause}")

        # Warnings
        validation_warnings = state.get("validation_warnings", [])
        if validation_warnings:
            parts.append(f"\n## Notes")
            for warning in validation_warnings[:3]:
                parts.append(f"- {warning}")

        return "\n".join(parts)

    async def process(self, input_data: AgentInput) -> AgentOutput:
        """Process a query through the orchestrator."""
        start_time = time.time()

        try:
            # Create initial state
            initial_state = create_initial_orchestrator_state(
                query=input_data.message,
                session_id=input_data.session_id,
                user_id=input_data.user_id
            )

            # Invoke graph (async because nodes are async)
            # NOTE: In LangSmith traces, this shows as "LangGraph" (framework name) but it IS the orchestrator
            # The trace structure is: LangGraph → routing → gate → invoke_agents → diagnosis → early_exit
            from langchain_core.runnables import RunnableConfig
            
            config = RunnableConfig(
                tags=["orchestrator", "routeflow"],
                metadata={"agent_name": "orchestrator", "query": input_data.message[:100]}
            )
            
            logger.info("Invoking orchestrator graph", query=input_data.message[:50])
            final_state = await self.graph.ainvoke(initial_state, config=config)

            execution_time_ms = int((time.time() - start_time) * 1000)

            logger.info(
                "Orchestrator completed",
                execution_time_ms=execution_time_ms,
                confidence=final_state.get("confidence", 0.0)
            )

            return AgentOutput(
                response=final_state["final_response"],
                agent_name=self.agent_name,
                reasoning="\n".join(final_state.get("reasoning_steps", [])),
                tools_used=final_state.get("tools_used", []),
                confidence=final_state.get("confidence", 0.0),
                metadata={
                    "execution_time_ms": execution_time_ms,
                    "agents_invoked": list(final_state.get("agent_results", {}).keys()),
                    "severity": final_state.get("severity_assessment", ""),
                    "recommendations_count": len(final_state.get("validated_recommendations", []))
                }
            )

        except Exception as e:
            logger.error("Orchestrator failed", error_message=str(e))
            execution_time_ms = int((time.time() - start_time) * 1000)

            return AgentOutput(
                response=f"I encountered an error processing your request: {str(e)}",
                agent_name=self.agent_name,
                reasoning=f"Error: {str(e)}",
                tools_used=[],
                confidence=0.0,
                metadata={"execution_time_ms": execution_time_ms, "error": str(e)}
            )


    async def _emit_progress(self, phase: str, status: str, details: Dict[str, Any] = None):
        """Emit progress event if callback is set."""
        if self._progress_callback:
            elapsed_ms = int((time.time() - self._start_time) * 1000)
            await self._progress_callback(phase, status, {
                **(details or {}),
                "elapsed_ms": elapsed_ms
            })

    async def invoke_with_progress(
        self,
        input_data: AgentInput,
        on_progress: ProgressCallback
    ) -> AgentOutput:
        """
        Invoke orchestrator with progress callbacks at each phase.

        Args:
            input_data: The agent input
            on_progress: Async callback called with (phase, status, details)
                        - phase: routing, gate, invoke_agents, diagnosis, recommendation, validation, generate_response
                        - status: started, running, completed
                        - details: dict with message and phase-specific data

        Returns:
            AgentOutput with the final response
        """
        self._start_time = time.time()
        self._progress_callback = on_progress

        try:
            # Create initial state
            initial_state = create_initial_orchestrator_state(
                query=input_data.message,
                session_id=input_data.session_id,
                user_id=input_data.user_id
            )

            # Invoke graph (async because nodes are async)
            from langchain_core.runnables import RunnableConfig

            config = RunnableConfig(
                tags=["orchestrator", "routeflow", "streaming"],
                metadata={"agent_name": "orchestrator", "query": input_data.message[:100]}
            )

            logger.info("Invoking orchestrator graph with progress", query=input_data.message[:50])
            final_state = await self.graph.ainvoke(initial_state, config=config)

            execution_time_ms = int((time.time() - self._start_time) * 1000)

            logger.info(
                "Orchestrator with progress completed",
                execution_time_ms=execution_time_ms,
                confidence=final_state.get("confidence", 0.0)
            )

            return AgentOutput(
                response=final_state["final_response"],
                agent_name=self.agent_name,
                reasoning="\n".join(final_state.get("reasoning_steps", [])),
                tools_used=final_state.get("tools_used", []),
                confidence=final_state.get("confidence", 0.0),
                metadata={
                    "execution_time_ms": execution_time_ms,
                    "agents_invoked": list(final_state.get("agent_results", {}).keys()),
                    "severity": final_state.get("severity_assessment", ""),
                    "recommendations_count": len(final_state.get("validated_recommendations", [])),
                    "routing_decision": final_state.get("routing_decision", {}),
                    "diagnosis": final_state.get("diagnosis", {}),
                    "recommendations": final_state.get("validated_recommendations", []),
                    "gate_warnings": final_state.get("gate_result", {}).get("warnings", []),
                }
            )

        except Exception as e:
            logger.error("Orchestrator with progress failed", error_message=str(e))
            execution_time_ms = int((time.time() - self._start_time) * 1000)

            return AgentOutput(
                response=f"I encountered an error processing your request: {str(e)}",
                agent_name=self.agent_name,
                reasoning=f"Error: {str(e)}",
                tools_used=[],
                confidence=0.0,
                metadata={"execution_time_ms": execution_time_ms, "error": str(e)}
            )

        finally:
            self._progress_callback = None


# Global instance
orchestrator = Orchestrator()
