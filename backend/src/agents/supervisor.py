"""
Super Simple Supervisor - Exact Tutorial Pattern
"""
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from typing import Literal, TypedDict, List, Annotated, Optional
from langchain_core.language_models.chat_models import BaseChatModel

from ..schemas.agent_state import State
from ..schemas.agent import AgentInput, AgentOutput
from ..tools.snowflake_tools import ALL_SNOWFLAKE_TOOLS
from ..core.config import settings
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic


# Get LLM
def get_llm() -> BaseChatModel:
    if settings.anthropic_api_key:
        return ChatAnthropic(model=settings.anthropic_model, temperature=0.1)
    elif settings.openai_api_key:
        return ChatOpenAI(model=settings.openai_model, temperature=0.1)
    else:
        raise ValueError("No LLM API key configured - set ANTHROPIC_API_KEY or OPENAI_API_KEY")

llm = get_llm()


# Create agents directly (tutorial pattern)
budget_agent = create_react_agent(
    llm,
    tools=ALL_SNOWFLAKE_TOOLS,
    prompt=(
        "You are a budget analysis agent. Use execute_custom_snowflake_query to query "
        "reports.multi_agent.DV360_BUDGETS_QUIZ table. All column names must be UPPERCASE. "
        "Don't ask follow up questions."
    )
)

performance_agent = create_react_agent(
    llm,
    tools=ALL_SNOWFLAKE_TOOLS,
    prompt=(
        "You are a performance analysis agent. Use execute_custom_snowflake_query to query "
        "reports.reporting_revamp.ALL_PERFORMANCE_AGG table. Always filter WHERE ADVERTISER = 'Quiz'. "
        "Exclude today's date - use DATE < CURRENT_DATE(). All column names must be UPPERCASE. "
        "Don't ask follow up questions."
    )
)


# Supervisor node (tutorial pattern)
def make_supervisor_node(llm: BaseChatModel, members: List[str]):
    """Create a supervisor node that routes to worker agents.

    Args:
        llm: The language model to use for routing decisions
        members: List of worker agent names (e.g., ["budget", "performance"])

    Returns:
        A supervisor node function for the graph
    """
    options = ["FINISH"] + members
    system_prompt = (
        "You are a SUPERVISOR with full control over coordinating workers and managing the conversation.\n\n"
        f"You manage these workers: {members}.\n\n"
        "YOUR CAPABILITIES:\n"
        "1. ROUTE to workers when they need to perform tasks\n"
        "2. SYNTHESIZE responses when you have enough information from workers\n"
        "3. COORDINATE between workers when the request needs multiple agents\n"
        "4. PROVIDE FINAL ANSWERS by combining worker outputs\n"
        "5. ASK FOR CLARIFICATION when the request is unclear\n\n"
        "ROUTING RULES:\n"
        "- Route to 'budget' if the user asks about budgets, spending, allocation, or financial data.\n"
        "- Route to 'performance' if the user asks about campaign performance, metrics, impressions, clicks, conversions, or revenue.\n"
        "- If the user's request mentions BOTH performance AND budgets, route to 'performance' FIRST, then 'budget'.\n\n"
        "WHEN TO PROVIDE YOUR OWN RESPONSE (supervisor_response):\n"
        "- When you have responses from multiple workers and need to synthesize them\n"
        "- When you need to coordinate between worker outputs\n"
        "- When you can provide a complete answer by combining worker responses\n"
        "- When providing a final summary after all workers have responded\n"
        "- Set next='FINISH' and provide supervisor_response\n\n"
        "WHEN TO FINISH:\n"
        "- If you provided a supervisor_response that answers the user's question completely\n"
        "- If ALL required workers have responded and you've synthesized their outputs\n"
        "- If the user's message is unclear - provide clarification and FINISH\n"
        "- Never FINISH without a response unless asking for clarification"
    )

    # Create Router class with dynamic options
    # Note: We use Annotated to provide the valid options to the LLM
    class Router(TypedDict):
        """Router decision - supervisor has full control over routing and responses."""
        next: Annotated[str, f"Must be one of: {', '.join(options)}"]
        clarification: Annotated[str, "If next is FINISH and the user's message is unclear, provide a friendly clarification question. Otherwise empty string."]
        supervisor_response: Annotated[str, "If you want to provide a response yourself (synthesize agent outputs, coordinate, or provide final answer), provide it here. Otherwise empty string. Use this when you need to combine multiple agent responses or provide coordination."]

    def supervisor_node(state: State) -> Command:
        """Supervisor decides which agent to call next."""
        # Check max iterations limit
        iteration_count = state.get("iteration_count", 0)
        if iteration_count >= 5:
            return Command(
                goto=END,
                update={"next": "FINISH", "iteration_count": iteration_count + 1}
            )
        
        # Check if all required agents have completed
        budget_complete = state.get("budget_complete", False)
        performance_complete = state.get("performance_complete", False)
        agents_called = state.get("agents_called", [])
        
        # If both agents completed, FINISH
        if budget_complete and performance_complete:
            return Command(
                goto=END,
                update={"next": "FINISH", "iteration_count": iteration_count + 1}
            )
        
        # Build context for supervisor decision
        context_parts = []
        if agents_called:
            context_parts.append(f"Agents already called: {', '.join(agents_called)}")
        if budget_complete:
            context_parts.append("Budget agent has completed its task")
        if performance_complete:
            context_parts.append("Performance agent has completed its task")
        
        context = "\n".join(context_parts) if context_parts else "No agents called yet."
        
        # Build messages: system prompt + conversation history
        messages = [
            SystemMessage(content=system_prompt + f"\n\nCurrent state: {context}\nIteration count: {iteration_count}/5")
        ] + state["messages"]

        response = llm.with_structured_output(Router).invoke(messages)
        goto = response["next"]
        clarification = response.get("clarification", "")
        supervisor_response = response.get("supervisor_response", "")

        # Validate the response is a valid option
        if goto not in options:
            # Default to FINISH if invalid response
            goto = "FINISH"

        # If supervisor wants to provide its own response (synthesize/coordinate)
        if supervisor_response and goto == "FINISH":
            return Command(
                goto=END,
                update={
                    "next": "FINISH",
                    "iteration_count": iteration_count + 1,
                    "messages": [
                        HumanMessage(
                            content=supervisor_response,
                            name="supervisor"
                        )
                    ]
                }
            )

        # If supervisor needs clarification, generate response and FINISH
        if goto == "FINISH" and clarification:
            return Command(
                goto=END,
                update={
                    "next": "FINISH",
                    "iteration_count": iteration_count + 1,
                    "messages": [
                        HumanMessage(
                            content=clarification,
                            name="supervisor"
                        )
                    ]
                }
            )

        if goto == "FINISH":
            goto = END

        # Update agents_called list
        new_agents_called = list(agents_called)
        if goto in members and goto not in new_agents_called:
            new_agents_called.append(goto)

        return Command(
            goto=goto,
            update={
                "next": response["next"],
                "iteration_count": iteration_count + 1,
                "agents_called": new_agents_called
            }
        )

    return supervisor_node


# Budget node (async for async tools)
async def budget_node(state: State) -> Command[Literal["supervisor"]]:
    result = await budget_agent.ainvoke(state)
    
    # Check if agent response indicates completion
    agent_response = result["messages"][-1].content
    task_complete = any(phrase in agent_response.lower() for phrase in [
        "complete", "finished", "done", "summary", "conclusion", "final"
    ]) or len(agent_response) > 200  # Substantial response likely means complete
    
    return Command(
        update={
            "messages": [
                HumanMessage(content=agent_response, name="budget")
            ],
            "budget_complete": task_complete
        },
        goto="supervisor",
    )


# Performance node (async for async tools)
async def performance_node(state: State) -> Command[Literal["supervisor"]]:
    result = await performance_agent.ainvoke(state)
    
    # Check if agent response indicates completion
    agent_response = result["messages"][-1].content
    task_complete = any(phrase in agent_response.lower() for phrase in [
        "complete", "finished", "done", "summary", "conclusion", "final"
    ]) or len(agent_response) > 200  # Substantial response likely means complete
    
    return Command(
        update={
            "messages": [
                HumanMessage(content=agent_response, name="performance")
            ],
            "performance_complete": task_complete
        },
        goto="supervisor",
    )


# Build graph (tutorial pattern)
members = ["budget", "performance"]
supervisor_node = make_supervisor_node(llm, members)

super_builder = StateGraph(State)
super_builder.add_node("supervisor", supervisor_node)
super_builder.add_node("budget", budget_node)
super_builder.add_node("performance", performance_node)
super_builder.add_edge(START, "supervisor")

super_graph = super_builder.compile()

# Export as a simple namespace
class Supervisor:
    """Simple namespace for the supervisor graph and invoke function."""
    graph = super_graph

    @staticmethod
    async def invoke(
        agent_input: AgentInput,
        previous_messages: Optional[List] = None
    ) -> AgentOutput:
        """Invoke supervisor with optional previous message history."""
        from ..core.session_manager import save_messages_from_state
        
        # Build initial messages: previous + new user message
        initial_messages = []
        if previous_messages:
            initial_messages.extend(previous_messages)
        initial_messages.append(HumanMessage(content=agent_input.message))
        
        initial_state = {
            "messages": initial_messages,
            "next": None,
            "session_id": agent_input.session_id,
            "user_id": agent_input.user_id,
            "iteration_count": 0,
            "agents_called": [],
            "budget_complete": False,
            "performance_complete": False
        }

        final_state = await super_graph.ainvoke(initial_state)

        # Save only NEW messages to database (not the ones we loaded)
        if agent_input.session_id:
            final_messages = final_state.get("messages", [])
            
            # Track which messages we started with (by content + role + agent_name)
            if previous_messages:
                previous_signatures = set()
                for msg in previous_messages:
                    if not hasattr(msg, 'content'):
                        continue
                    role = 'user' if isinstance(msg, HumanMessage) else 'assistant' if isinstance(msg, AIMessage) else 'system'
                    agent_name = getattr(msg, 'name', None) if isinstance(msg, AIMessage) else None
                    sig = (msg.content, role, agent_name)
                    previous_signatures.add(sig)
            else:
                previous_signatures = set()
            
            # Only save messages that are NEW (not in previous_signatures)
            # Always include user messages (even if duplicate content - user can send same message multiple times)
            new_messages = []
            for msg in final_messages:
                if not hasattr(msg, 'content') or not msg.content:
                    continue
                
                role = 'user' if isinstance(msg, HumanMessage) else 'assistant' if isinstance(msg, AIMessage) else 'system'
                agent_name = getattr(msg, 'name', None) if isinstance(msg, AIMessage) else None
                sig = (msg.content, role, agent_name)
                
                # Always include user messages (allow duplicates)
                # Only filter assistant/system messages
                if role == 'user' or sig not in previous_signatures:
                    new_messages.append(msg)
            
            if new_messages:
                await save_messages_from_state(
                    session_id=agent_input.session_id,
                    messages=new_messages
                )

        # Get last message content
        messages = final_state.get("messages", [])
        final_response = messages[-1].content if messages else "No response"

        return AgentOutput(
            response=final_response,
            agent_name="supervisor",
            reasoning="",
            tools_used=[],
            confidence=0.9
        )


supervisor = Supervisor()

# Export graph directly for visualization
__all__ = ['supervisor', 'super_graph']
