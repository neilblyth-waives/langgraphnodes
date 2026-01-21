# Recent Changes & Updates

**Last Updated**: 2026-01-21
**Status**: Current implementation details

**Note**: This document tracks recent changes. For complete system overview, see `COMPLETE_SYSTEM_SUMMARY.md`.

---

## Overview

This document tracks recent changes and improvements to the DV360 Agent System. For historical context, see `ROUTEFLOW_MIGRATION_COMPLETE.md`.

---

## 🎯 Latest Changes (2026-01-21)

### Conversation History / Memory Context

**Files Modified**: All specialist agents + orchestrator + routing_agent

**Change**: All agents now have access to conversation history for contextual understanding

**Implementation**:
- Orchestrator fetches conversation history from `session_manager.get_messages()`
- History is passed to agents via `input_data.context["conversation_history"]`
- Last 10 messages included (to avoid token limits)
- Format: `[Previous] user message` and `[Previous Response] assistant response`

**Agents Updated**:
- ✅ `performance_agent_simple.py`
- ✅ `audience_agent_simple.py`
- ✅ `creative_agent_simple.py`
- ✅ `budget_risk_agent.py`
- ✅ `routing_agent.py`

**Code Pattern**:
```python
# In agent's process() method:
conversation_history = input_data.context.get("conversation_history", []) if input_data.context else []
if conversation_history:
    for msg in conversation_history[-10:]:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=f"[Previous] {content}"))
        elif role == "assistant":
            messages.append(AIMessage(content=f"[Previous Response] {content}"))
```

**Benefits**:
- Agents understand follow-up questions
- Better context for ambiguous queries
- Enables multi-turn conversations

---

### Enhanced Routing with Conversation Context

**File**: `backend/src/agents/routing_agent.py`

**Change**: Routing agent now uses conversation history to interpret follow-up queries

**Key Improvements**:
1. **Follow-up Query Handling**: Short queries like "budget", "yes", "that one" are interpreted in conversation context
2. **Date Range Interpretation**: When user provides dates, router looks at conversation context to determine intent
3. **Clarification Flow**: Routes to clarification instead of guessing when query is unclear

**New Routing Logic**:
```
CONVERSATION HISTORY (recent messages for context):
- If user's query is short, interpret it in context of previous messages
- If assistant asked for clarification, user's response answers that question
- If user provides date ranges, use context to determine agent:
  * Previous "performance" → performance_diagnosis
  * Previous "budget" → budget_risk
  * Previous "audience" → audience_targeting
  * Previous "creative" → creative_inventory
  * No context → default to performance_diagnosis
```

**Clarification Handling**:
- `AGENTS: NONE` when query is unclear
- `CONFIDENCE: 0.0` for unclear queries
- `CLARIFICATION:` line provides helpful question
- Ignores "None", "N/A", "not needed" clarification values

---

### Orchestrator Clarification Flow

**File**: `backend/src/agents/orchestrator.py`

**Change**: New conditional routing path for clarification requests

**Flow Update**:
```
routing → [clarification_needed?]
    ├─ YES → generate_response (skip all other phases)
    └─ NO → gate → invoke_agents → ...
```

**Key Changes**:
1. `_routing_decision()` checks for `clarification_needed` flag
2. Clarification skips gate, agents, diagnosis, recommendations
3. `clarification_message` passed directly to response

**Benefits**:
- Faster response for unclear queries
- No wasted agent calls when clarification needed
- Better user experience

---

### Progress Callbacks

**File**: `backend/src/agents/orchestrator.py`

**Change**: New `invoke_with_progress()` method for real-time progress updates

**API**:
```python
async def invoke_with_progress(
    self,
    input_data: AgentInput,
    on_progress: Callable[[str, str, Dict], Awaitable[None]]
) -> AgentOutput
```

**Progress Events**:
- `routing` - started, completed
- `gate` - started, completed
- `invoke_agents` - started, running (per agent), completed
- `diagnosis` - started, completed (or skipped)
- `recommendation` - started, completed
- `validation` - started, completed
- `generate_response` - started, completed

**Usage**: For streaming/SSE endpoints to show real-time progress

---

### Critical Date Handling Rules

**Files Modified**: All agent system prompts + `snowflake_tools.py`

**Change**: Comprehensive date handling rules added to all agents

**Rules**:
1. **No Data for Today**: Data only available up to YESTERDAY
2. **Always Exclude Today**: `DATE < CURRENT_DATE()` or `DATE <= DATEADD(day, -1, CURRENT_DATE())`
3. **"Last N Days"**: Query N+1 days back to yesterday
   - Example: "last 7 days" = `DATE >= DATEADD(day, -8, CURRENT_DATE()) AND DATE < CURRENT_DATE()`
4. **"Last Full Reporting Week"**: Dynamic calculation of Sunday-Saturday
   - Performance agent calculates exact dates dynamically

**Example (Performance Agent)**:
```python
# Calculate last full reporting week (Sunday-Saturday)
days_since_saturday = (now.weekday() + 2) % 7
last_saturday = now - timedelta(days=days_since_saturday)
last_sunday = last_saturday - timedelta(days=6)
```

---

### SQL Column Name Case Sensitivity

**File**: `backend/src/tools/snowflake_tools.py`

**Change**: Added `normalize_sql_column_names()` function to automatically uppercase column names

**Why**: Snowflake is case-sensitive for column names

**Implementation**:
- Parses SELECT, GROUP BY, ORDER BY clauses
- Uppercases identifiers while preserving:
  - Quoted strings ('Quiz')
  - SQL keywords (SELECT, FROM, WHERE)
  - Function names (SUM, COUNT, EXTRACT)

**Agent Prompts Updated**:
- All agents now document: "ALL column names MUST be UPPERCASE"
- Examples use UPPERCASE: `INSERTION_ORDER`, `SPEND_GBP`, `DATE`

---

### ReAct Agent Recursion Limit

**Files Modified**: All ReAct agents

**Change**: Added `RunnableConfig(recursion_limit=15)` to prevent infinite retry loops

**Code**:
```python
from langchain_core.runnables import RunnableConfig
config = RunnableConfig(recursion_limit=15)
result = await react_agent.ainvoke({"messages": messages}, config=config)
```

**Benefits**:
- Prevents infinite loops when SQL errors occur
- Graceful failure with error message
- Better error handling for max iterations

---

### Currency Documentation

**Files Modified**: All agent system prompts

**Change**: Explicit documentation that all financial values are in British Pounds (GBP/£)

**Updated Prompts**:
```
CURRENCY: All spend, revenue, and financial values are in BRITISH POUNDS (GBP/£).
Always display amounts with £ symbol or specify "GBP" when presenting financial data.
```

**Affected Columns**:
- `SPEND_GBP` - Daily/total spend in £
- `TOTAL_REVENUE_GBP_PM` - Revenue in £
- `BUDGET_AMOUNT` - Budget in £
- `AVG_DAILY_BUDGET` - Daily budget in £

---

### Follow-up Query Diagnosis Skip

**File**: `backend/src/agents/orchestrator.py`

**Change**: Diagnosis is skipped for follow-up queries (answers to clarification questions)

**Detection**:
```python
follow_up_phrases = ["yes i do", "yes", "no", "that one", "the first", "the second", "re run", "point 1"]
is_follow_up = any(phrase in query.lower() for phrase in follow_up_phrases)
```

**Benefits**:
- Faster response for follow-ups
- Avoids meaningless diagnosis of "yes" or "no"
- Uses agent response directly as output

---

## 🎯 Latest Changes (2026-01-15)

### BaseAgent Cleanup - Removed Unused Methods

**File**: `backend/src/agents/base.py`

**Change**: Removed 2 unused helper methods

**Removed Methods**:
- ❌ `_format_messages()` - Convert dict messages to LangChain objects (never used)
- ❌ `_build_context()` - Format context string from memories (never used)

**Kept Method**:
- ✅ `invoke()` - Wrapper with logging/error handling (actively used by orchestrator)

**Impact**: 
- Reduced `base.py` from 247 lines to 200 lines (47 lines removed)
- Cleaner codebase with only actively used methods
- No functionality lost (methods were never called)

**Rationale**:
- Agents create messages directly using `SystemMessage()`, `HumanMessage()` - no need for conversion
- Agents handle context building in their own `process()` methods
- `invoke()` remains as it's the standard entry point used by orchestrator

---

## 🎯 Latest Changes (2026-01-15)

### Tool Consolidation - Single Custom Query Tool

**Files**: 
- `backend/src/tools/snowflake_tools.py`
- `backend/src/tools/agent_tools.py`
- `backend/src/tools/__init__.py`

**Change**: Removed 4 bespoke query tools, consolidated to single `execute_custom_snowflake_query`

**Removed Tools**:
- ❌ `query_campaign_performance`
- ❌ `query_budget_pacing`
- ❌ `query_audience_performance`
- ❌ `query_creative_performance`

**Kept Tool**:
- ✅ `execute_custom_snowflake_query` - **ONLY Snowflake query tool**

**Rationale**:
- Agents have complete schema information in system prompts
- LLM can build SQL queries dynamically
- More flexible than pre-built query functions
- Easier to maintain (one tool vs five)

**Impact**: 
- All agents now build SQL queries themselves
- Enhanced `execute_custom_snowflake_query` with complete schema documentation
- Created `docs/SNOWFLAKE_SCHEMA_REFERENCE.md` for reference

---

### Agent Cleanup - Removed Legacy Agents

**Files Removed**:
- ❌ `backend/src/agents/conductor.py` (~420 lines)
- ❌ `backend/src/agents/performance_agent.py` (~500 lines)
- ❌ `backend/src/agents/audience_agent.py` (~400 lines)
- ❌ `backend/src/agents/creative_agent.py` (~500 lines)
- ❌ `backend/src/agents/performance_agent_langgraph.py` (~660 lines)

**Total Removed**: ~2,480 lines of unused code

**Why Removed**:
- Legacy agents only used by `conductor.py` (which isn't used)
- Replaced by simpler ReAct agents (`*_agent_simple.py`)
- Orchestrator uses simple ReAct agents, not legacy ones

**Active Agents** (Kept):
- ✅ `performance_agent_simple.py` - ReAct-based performance agent
- ✅ `audience_agent_simple.py` - ReAct-based audience agent
- ✅ `creative_agent_simple.py` - ReAct-based creative agent
- ✅ `budget_risk_agent.py` - ReAct-based budget agent
- ✅ `delivery_agent_langgraph.py` - LangGraph delivery agent

**Impact**:
- Cleaner codebase
- Less confusion about which agents are active
- Easier maintenance

---

### Diagnosis Optimization

**File**: `backend/src/agents/orchestrator.py`

**Change**: Skip diagnosis for single-agent informational queries

**Optimization**:
- Detects informational queries ("what is", "how is", "show me")
- If only 1 agent invoked AND query is informational → skip diagnosis
- Uses agent response directly as diagnosis summary

**Time Savings**: ~4.5 seconds (23% reduction for simple queries)

**Code**:
```python
if len(approved_agents) == 1 and self._is_informational_query(query):
    # Skip diagnosis, use agent response directly
    diagnosis = {"summary": agent_output.response, "severity": "low", ...}
```

---

### State Management Improvements

**File**: `backend/src/agents/orchestrator.py`

**Change**: Use `gate_result` as single source of truth

**Before**: Stored redundant data
```python
{
    "gate_result": {...},
    "approved_agents": [...],  # Duplicate
    "gate_warnings": [...]     # Duplicate
}
```

**After**: Single source of truth
```python
{
    "gate_result": {...}  # Contains approved_agents, warnings, etc.
}
```

**Access Pattern**: `state["gate_result"]["approved_agents"]`

---

### Snowflake Tool Cleanup

**File**: `backend/src/tools/snowflake_tool.py`

**Removed Unused Methods**:
- ❌ `get_campaign_performance()` - Not used (removed tool)
- ❌ `get_budget_pacing()` - Not used (removed tool)
- ❌ `get_audience_performance()` - Not used (removed tool)
- ❌ `get_creative_performance()` - Not used (removed tool)

**Kept**:
- ✅ `execute_query()` - Core query execution
- ✅ Connection logic
- ✅ Authentication logic
- ✅ Query caching

**Impact**: Reduced from ~420 lines to ~212 lines

---

## 🎯 Major Changes (2026-01-15)

### 1. Budget Risk Agent Simplified to ReAct Pattern

**File**: `backend/src/agents/budget_risk_agent.py`

**Change**: Refactored from 450 lines to 116 lines (74% reduction)

**Before**: 
- Custom LangGraph workflow with separate nodes
- Manual metric calculations (`_analyze_budget_pacing`)
- Rule-based recommendations (`_generate_recommendations`)
- Complex prompt building
- Regex-based ID extraction

**After**:
- Simple ReAct agent wrapper
- LLM handles all analysis and recommendations
- Direct access to `execute_custom_snowflake_query`
- Minimal code, maximum flexibility

**Impact**: 
- Easier to maintain
- More flexible (LLM builds SQL dynamically)
- Faster to modify behavior

**Code Pattern**:
```python
react_agent = create_react_agent(
    model=self.llm,
    tools=tools  # Includes execute_custom_snowflake_query
)
result = await react_agent.ainvoke({
    "messages": [
        SystemMessage(content=self.get_system_prompt()),
        HumanMessage(content=input_data.message)
    ]
})
```

---

### 2. Universal SQL Query Capability

**Files**: 
- `backend/src/tools/agent_tools.py`
- All agent system prompts

**Change**: All agents now have access to `execute_custom_snowflake_query`

**Agents Updated**:
- ✅ Performance Agent
- ✅ Budget Risk Agent (already had it)
- ✅ Audience Agent
- ✅ Creative Agent
- ✅ Delivery Agent

**Benefits**:
- Agents can build custom SQL queries dynamically
- No need to pre-build every query type
- LLM decides what data it needs and builds the query

**Table Context**: Each agent knows its primary table(s):
- **Budget Agent**: `reports.multi_agent.DV360_BUDGETS_QUIZ` (primary)
- **Performance Agent**: `reports.reporting_revamp.ALL_PERFORMANCE_AGG`
- **Delivery Agent**: `reports.reporting_revamp.creative_name_agg` + `ALL_PERFORMANCE_AGG`

---

### 3. Dynamic Date Awareness

**Files**: All agent system prompts

**Change**: All agents now use `datetime.now()` for current date awareness

**Updated Agents**:
- Orchestrator
- Routing Agent
- Budget Risk Agent
- Performance Agent
- Delivery Agent

**Implementation**:
```python
from datetime import datetime
current_date = datetime.now().strftime("%B %Y")
current_year = datetime.now().year

# In system prompt:
f"IMPORTANT: The current date is {current_date} (year {current_year})..."
```

**Why**: 
- Models trained in 2024 don't know it's 2026
- Prevents queries defaulting to old dates (e.g., 2023)
- Ensures date filters use current year/month

---

### 4. Budget Pacing Tool Updated

**Files**: 
- `backend/src/tools/snowflake_tool.py`
- `backend/src/tools/snowflake_tools.py`
- `backend/src/agents/budget_risk_agent.py`

**Changes**:

#### Correct Column Names
- ✅ Changed `campaign_id` → `INSERTION_ORDER_ID`
- ✅ Changed `date` → `SEGMENT_START_DATE` / `SEGMENT_END_DATE`
- ✅ Added `io_name` parameter for filtering by insertion order name

#### Available Columns Documented
```
- INSERTION_ORDER_ID: Insertion order ID
- IO_NAME: Insertion order name (e.g., "Quiz for Jan")
- IO_STATUS: Insertion order status
- SEGMENT_NUMBER: Monthly segment number
- BUDGET_AMOUNT: Total budget for the monthly segment
- SEGMENT_START_DATE: Start date of monthly segment
- SEGMENT_END_DATE: End date of monthly segment
- DAYS_IN_SEGMENT: Number of days in segment
- AVG_DAILY_BUDGET: Average daily budget for the segment
- SEGMENT_STATUS: Budget segment status
```

#### Context Added
- **Quiz Advertiser**: All budgets are for advertiser 'Quiz' only (hardcoded for testing)
- **Monthly Budgets**: Budgets are at MONTHLY level (each row = one monthly segment)
- **Date Defaults**: Defaults to current date if not specified (not 2023!)

**Method Signature**:
```python
async def get_budget_pacing(
    insertion_order_id: Optional[str] = None,
    io_name: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> List[Dict[str, Any]]  # Returns list of monthly segments
```

---

### 5. Snowflake Tool Cleanup

**File**: `backend/src/tools/snowflake_tool.py`

**Changes**:

#### Removed Unused Code
- ❌ Removed `to_langchain_tool()` method (never used)

#### Fixed Bugs
- ✅ Fixed duplicate date filtering in `get_audience_performance()` (lines 313-316 removed)
- ✅ Added Decimal → float conversion for JSON serialization

**Decimal Serialization Fix**:
```python
# In _execute_query_sync():
elif isinstance(value, Decimal):
    serializable_row[key] = float(value)  # Convert Decimal to float
```

**Impact**: Prevents `Object of type Decimal is not JSON serializable` errors

---

### 6. Agent System Prompts Enhanced

**Files**: All agent system prompts

**Additions**:

1. **Table Context**: Each agent knows its primary table(s)
2. **Date Awareness**: Dynamic current date/year
3. **Column Documentation**: Budget agent knows all 10 columns
4. **Testing Context**: Quiz advertiser, monthly budgets

**Example (Budget Agent)**:
```
IMPORTANT: The current date is January 2026 (year 2026). 
All date references should be interpreted relative to 2026.

PRIMARY TABLE: reports.multi_agent.DV360_BUDGETS_QUIZ

Available columns:
- INSERTION_ORDER_ID, IO_NAME, IO_STATUS, SEGMENT_NUMBER,
- BUDGET_AMOUNT, SEGMENT_START_DATE, SEGMENT_END_DATE,
- DAYS_IN_SEGMENT, AVG_DAILY_BUDGET, SEGMENT_STATUS

IMPORTANT CONTEXT:
- All budgets are for advertiser 'Quiz' only
- Budgets are at MONTHLY level (each row = one monthly segment)
```

---

## 🔧 Technical Details

### Model Configuration
- **LLM**: Claude 3 Haiku (`claude-3-haiku-20240307`)
- **Training Date**: March 2024
- **Current Date Context**: January 2026 (dynamic)
- **Why Date Context Matters**: Model doesn't know current date, so we inject it

### Testing Context
- **Advertiser**: Quiz (hardcoded in queries for testing)
- **Budget Level**: Monthly segments
- **Date Range**: Defaults to current year/month if not specified

### Code Patterns

#### ReAct Agent Pattern (Budget Agent)
```python
# Simple ReAct wrapper
react_agent = create_react_agent(model=self.llm, tools=tools)
result = await react_agent.ainvoke({"messages": [SystemMessage(...), HumanMessage(...)]})
```

#### Dynamic Date in Prompts
```python
from datetime import datetime
current_date = datetime.now().strftime("%B %Y")
current_year = datetime.now().year
# Use in f-string
```

#### Custom SQL Query Tool
```python
# All agents can use:
execute_custom_snowflake_query(query="SELECT ... FROM reports.multi_agent.DV360_BUDGETS_QUIZ WHERE ...")
```

---

## 📊 Impact Summary

| Change | Lines Changed | Complexity | Maintainability |
|--------|--------------|------------|-----------------|
| Budget Agent Simplification | -334 lines | ⬇️ Reduced | ⬆️ Improved |
| Universal SQL Access | +5 tools | ➡️ Same | ⬆️ Improved |
| Dynamic Dates | +5 prompts | ➡️ Same | ⬆️ Improved |
| Budget Tool Update | ~50 lines | ➡️ Same | ⬆️ Improved |
| Snowflake Cleanup | -20 lines | ⬇️ Reduced | ⬆️ Improved |

**Total**: ~300 lines removed, better maintainability, more flexibility

---

## 🚀 Migration Notes

### For Developers

1. **Budget Agent**: Now uses ReAct pattern - no custom LangGraph nodes
2. **SQL Queries**: All agents can build custom SQL - check system prompts for table context
3. **Dates**: Always use current date context - don't hardcode years
4. **Testing**: Quiz advertiser hardcoded - will be parameterized later

### For AI Assistants

When working with this codebase:
- Budget agent is minimal ReAct (116 lines)
- All agents have `execute_custom_snowflake_query`
- Dates are dynamic (`datetime.now()`)
- Budget tool uses `INSERTION_ORDER_ID`, not `campaign_id`
- Budgets are monthly segments, not daily

---

## 📝 Next Steps

### Planned Improvements
- [ ] Parameterize advertiser (remove Quiz hardcoding)
- [ ] Add more budget analysis tools
- [ ] Document all Snowflake table schemas
- [ ] Add date range validation
- [ ] Create agent-specific query templates

### Known Limitations
- Quiz advertiser hardcoded (testing only)
- Budget tool returns monthly segments only
- No spend data in budget table (need to join with performance table)

---

## 🔗 Related Documentation

- **SYSTEM_STATUS.md** - Current system status
- **COMPLETE_SYSTEM_SUMMARY.md** - Full system overview
- **SYSTEM_ARCHITECTURE_GUIDE.md** - Architecture deep dive
- **ROUTEFLOW_MIGRATION_COMPLETE.md** - Historical context
- **docs/SNOWFLAKE_TOOL_EXPLAINED.md** - Snowflake tool details

---

**Last Updated**: 2026-01-15  
**Maintained By**: Development Team

