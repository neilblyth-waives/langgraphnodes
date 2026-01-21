#!/usr/bin/env python3
"""
Simple graph visualization - shows the structure without importing dependencies.
"""
print("=" * 70)
print("SUPERVISOR GRAPH STRUCTURE")
print("=" * 70)

print("\n📊 Nodes:")
print("-" * 70)
print("  • START (entry point)")
print("  • supervisor (routes to budget/performance/FINISH)")
print("  • budget (queries Snowflake budget data)")
print("  • performance (queries Snowflake performance data)")
print("  • END (exit point)")

print("\n🔗 Edges:")
print("-" * 70)
print("  START → supervisor")
print("  supervisor → budget (conditional)")
print("  supervisor → performance (conditional)")
print("  supervisor → END (conditional)")
print("  budget → supervisor")
print("  performance → supervisor")

print("\n📈 Mermaid Diagram:")
print("-" * 70)
mermaid = """graph TD
    START([START]) --> supervisor{supervisor}
    supervisor -->|route to budget| budget[budget agent]
    supervisor -->|route to performance| performance[performance agent]
    supervisor -->|FINISH| END([END])
    budget --> supervisor
    performance --> supervisor
    
    style START fill:#90EE90
    style END fill:#FFB6C1
    style supervisor fill:#87CEEB
    style budget fill:#FFD700
    style performance fill:#FFD700"""
print(mermaid)
print("-" * 70)

print("\n📋 Graph Flow:")
print("-" * 70)
print("""
Flow: START → supervisor → budget/performance → supervisor → ... → END

1. START: Entry point
2. supervisor: 
   - Analyzes user request
   - Routes to 'budget' for budget queries
   - Routes to 'performance' for performance queries
   - Routes to 'END' when done
3. budget: Queries Snowflake budget data, returns to supervisor
4. performance: Queries Snowflake performance data, returns to supervisor
5. END: Graph completes
""")

print("\n" + "=" * 70)
print("💡 Copy the Mermaid diagram above to https://mermaid.live/ to visualize!")
print("=" * 70)

