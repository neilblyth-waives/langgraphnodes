# Future Improvements & Ideas

This document tracks improvements, optimizations, and features we want to implement but are not in the current sprint plan.

---

## Performance Optimizations

### 1. Snowflake Connection Pooling

**Status**: Not Implemented
**Priority**: High
**Effort**: Medium (2-3 hours)

**Current State**:
- Creates new connection for every query (~1-2s overhead)
- Not scalable for concurrent users
- Connection closes after each query

**Proposed Solution**:
- Implement connection pool with 5-10 persistent connections
- Reuse connections across queries (reduce latency to ~0ms)
- Add connection health checks and auto-refresh
- Set max connection lifetime to prevent stale connections

**Expected Benefits**:
- Reduce query response time by 1-2 seconds
- Handle 10-100 concurrent users efficiently
- Reduce load on Snowflake account

**Implementation Notes**:
- Use `queue.Queue` or custom pool manager
- Add connection validation before reuse
- Handle connection failures gracefully
- Consider per-worker connection vs shared pool

**Files to Modify**:
- `backend/src/tools/snowflake_tool.py`

**Reference**:
- Mentioned in Phase 2.4 of implementation plan
- Discovered during performance analysis of 4.2s response time

---

## Other Ideas

(Add more improvement ideas here as they come up)

---

## Notes

- Items here are not prioritized in any particular order (except within sections)
- Each item should have clear status, benefit, and effort estimate
- Move items to sprint plan when ready to implement
