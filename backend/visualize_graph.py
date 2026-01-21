#!/usr/bin/env python3
"""
Visualize the supervisor graph using LangGraph's built-in visualization.
Run from project root: python -m backend.visualize_graph
Or from backend: PYTHONPATH=. python visualize_graph.py
"""
import sys
import os
from pathlib import Path

# Get project root (parent of backend)
backend_dir = Path(__file__).parent
project_root = backend_dir.parent

# Add project root to path so imports work
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Change to project root for proper module resolution
os.chdir(str(project_root))

# Load environment variables (optional - API keys not needed for visualization)
try:
    from dotenv import load_dotenv
    load_dotenv(project_root / ".env")
except Exception:
    pass  # Not critical for visualization

# Import the graph (now using absolute imports)
from backend.src.agents.supervisor import super_graph

# Get the graph structure
graph = super_graph.get_graph()

# Print Mermaid diagram
print("=" * 70)
print("SUPERVISOR GRAPH - MERMAID DIAGRAM")
print("=" * 70)
print("\nCopy the diagram below to https://mermaid.live/ to visualize:\n")
print("-" * 70)
mermaid = graph.draw_mermaid()
print(mermaid)
print("-" * 70)

# Print graph structure
print("\n" + "=" * 70)
print("GRAPH STRUCTURE")
print("=" * 70)
print(f"\nNodes: {list(graph.nodes.keys())}")
print(f"\nEdges:")
for edge in graph.edges:
    print(f"  {edge.source} → {edge.target}")

print("\n" + "=" * 70)
print("💡 Tip: Visit https://mermaid.live/ and paste the Mermaid diagram above")
print("=" * 70)

