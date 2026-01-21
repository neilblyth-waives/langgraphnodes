# LangGraph Orchestrator Visualization

## Current Flow (Linear, One-Way)

```
                    ┌─────────────┐
                    │   START     │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────────┐
                    │    ROUTING      │ ← LLM routes query to agents
                    │  (routing_node) │
                    └──────┬──────────┘
                           │
                           ├─── clarification_needed? ──┐
                           │                              │
                           └─── proceed ──────────────────┼──┐
                                                           │  │
                                                           ▼  │
                                              ┌─────────────────┐
                                              │      GATE       │ ← Validates routing decision
                                              │  (gate_node)    │
                                              └────────┬────────┘
                                                       │
                                                       ├─── block ────┐
                                                       │              │
                                                       └─── proceed ──┼──┐
                                                                      │  │
                                                                      ▼  │
                                                         ┌──────────────────────┐
                                                         │   INVOKE AGENTS      │ ← Parallel execution
                                                         │ (invoke_agents_node) │    budget + performance
                                                         └──────────┬───────────┘
                                                                    │
                                                                    │ agent_results = {
                                                                    │   "budget_risk": AgentOutput(...),
                                                                    │   "performance_diagnosis": AgentOutput(...)
                                                                    │ }
                                                                    │
                                                                    ▼
                                                         ┌─────────────────────────────┐
                                                         │ DIAGNOSIS & RECOMMENDATION  │ ← Analyzes results
                                                         │(diagnosis_recommendation_   │    (NO VALIDATION!)
                                                         │        _node)               │
                                                         └──────────┬──────────────────┘
                                                                    │
                                                                    ├─── exit ────┐
                                                                    │             │
                                                                    └─── continue ──┼──┐
                                                                                    │  │
                                                                                    ▼  │
                                                                       ┌─────────────────────┐
                                                                       │    VALIDATION       │ ← Validates recommendations
                                                                       │ (validation_node)   │
                                                                       └──────────┬──────────┘
                                                                                  │
                                                                                  ▼
                                                                       ┌─────────────────────┐
                                                                       │ GENERATE RESPONSE   │ ← Final output
                                                                       │(generate_response_  │
                                                                       │       _node)        │
                                                                       └──────────┬──────────┘
                                                                                  │
                                                                                  ▼
                                                                             ┌─────────┐
                                                                             │   END   │
                                                                             └─────────┘
```

## Current Problem: No Coordination

### Flow Characteristics:
- ✅ **Linear**: One-way flow, no loops
- ❌ **No Parameter Extraction**: Agents interpret queries independently
- ❌ **No Result Validation**: Results passed directly to diagnosis
- ❌ **No Consistency Checking**: No comparison of agent outputs
- ❌ **No Feedback Loop**: Can't re-query agents with corrected parameters

### What Happens:
1. **Routing** → Selects agents (budget + performance)
2. **Gate** → Validates selection
3. **Invoke Agents** → Each agent gets RAW query:
   - Budget: "explain Quiz budgets vs performance... recently"
   - Performance: "explain Quiz budgets vs performance... recently"
4. **Agents Return** → Different interpretations:
   - Budget: "January 2026 budgets: £3,200"
   - Performance: "Last 7 days: £500 spend"
5. **Diagnosis** → Receives both, tries to compare incomparable data
6. **Response** → Recommendations based on mismatched data

## Proposed Flow (With Coordination & Loops)

```
                    ┌─────────────┐
                    │   START     │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────────┐
                    │    ROUTING      │
                    └──────┬──────────┘
                           │
                           ▼
                    ┌─────────────────┐
                    │      GATE       │
                    └──────┬──────────┘
                           │
                           ▼
                    ┌─────────────────────────────┐
                    │ EXTRACT & NORMALIZE          │ ← NEW: Extract time periods
                    │ PARAMETERS                   │    Normalize "recently" → "last_7_days"
                    │ (extract_parameters_node)    │    Store: normalized_params
                    └──────┬──────────────────────┘
                           │
                           │ normalized_params = {
                           │   "time_period": "last_7_days",
                           │   "start_date": "2026-01-10",
                           │   "end_date": "2026-01-17"
                           │ }
                           │
                           ▼
                    ┌──────────────────────┐
                    │   INVOKE AGENTS      │ ← Pass normalized parameters
                    │                      │    agent_input.context = normalized_params
                    └──────────┬───────────┘
                               │
                               │ agent_results = {
                               │   "budget_risk": AgentOutput(...),
                               │   "performance_diagnosis": AgentOutput(...)
                               │ }
                               │
                               ▼
                    ┌─────────────────────────────┐
                    │ VALIDATE & COORDINATE        │ ← NEW: Check consistency
                    │ RESULTS                      │    Extract time periods from responses
                    │ (coordinate_results_node)    │    Compare: match or mismatch?
                    └──────┬───────────────────────┘
                           │
                           ├─── mismatch ──┐
                           │                │
                           │                ▼
                           │    ┌──────────────────────┐
                           │    │ RE-QUERY AGENTS      │ ← NEW: Re-query with normalized params
                           │    │ (requery_agents_node) │    Loop back to invoke_agents
                           │    └──────────┬───────────┘
                           │               │
                           │               └─── Loop back ──┐
                           │                                  │
                           └─── match ────────────────────────┼──┐
                                                               │  │
                                                               ▼  │
                                                  ┌─────────────────────────────┐
                                                  │ DIAGNOSIS & RECOMMENDATION  │ ← Only receives validated data
                                                  └──────────┬──────────────────┘
                                                             │
                                                             ▼
                                                  ┌─────────────────────┐
                                                  │    VALIDATION       │
                                                  └──────────┬──────────┘
                                                             │
                                                             ▼
                                                  ┌─────────────────────┐
                                                  │ GENERATE RESPONSE   │
                                                  └──────────┬──────────┘
                                                             │
                                                             ▼
                                                        ┌─────────┐
                                                        │   END   │
                                                        └─────────┘
```

## Key Changes

### 1. New Nodes

| Node | Purpose | Location |
|------|---------|----------|
| `extract_parameters` | Extract & normalize query parameters | After `gate` |
| `coordinate_results` | Validate agent results for consistency | After `invoke_agents` |
| `requery_agents` | Re-invoke agents with normalized params | Loop back to `invoke_agents` |

### 2. New Edges

| Edge | Type | Purpose |
|------|------|---------|
| `gate → extract_parameters` | Direct | Pass validated routing to parameter extraction |
| `extract_parameters → invoke_agents` | Direct | Pass normalized params to agents |
| `invoke_agents → coordinate_results` | Direct | Pass agent results for validation |
| `coordinate_results → requery_agents` | Conditional | Loop back if mismatch detected |
| `coordinate_results → diagnosis_recommendation` | Conditional | Proceed if consistent |
| `requery_agents → coordinate_results` | Direct | Loop back to validate again |

### 3. New Decision Points

| Decision Point | Options | Logic |
|---------------|---------|-------|
| `coordination_decision` | `requery` OR `proceed` | If mismatch AND retries < max → requery, else proceed |

## Loop Prevention

```python
# Max 2 retries to prevent infinite loops
if state.get("requery_count", 0) >= 2:
    logger.warning("Max retries reached, proceeding with mismatched data")
    return "proceed"
```

## State Changes

Add to `OrchestratorState`:

```python
# Parameter extraction
normalized_params: Dict[str, Any]
extraction_confidence: float

# Coordination
coordination_result: Dict[str, Any]
agent_time_periods: Dict[str, str]
requery_count: int
max_requeries: int  # Default: 2
```

## Benefits

1. ✅ **Consistency**: All agents use same time periods
2. ✅ **Validation**: Detects mismatches before diagnosis
3. ✅ **Self-correction**: Can re-query with normalized params
4. ✅ **Better recommendations**: Based on comparable data
5. ✅ **Transparency**: User knows if data is comparable

## Trade-offs

### Pros
- Ensures data consistency
- Better recommendations
- Self-correcting

### Cons
- More complexity
- Additional LLM calls (parameter extraction)
- Potential for loops (mitigated by retry limits)
- Slightly slower (but more accurate)

