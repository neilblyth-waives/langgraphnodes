"""
Simple script to visualize the supervisor graph.
Run from backend directory: python show_graph.py
"""
import sys
from pathlib import Path

# Setup path
backend = Path(__file__).parent
sys.path.insert(0, str(backend))

# Load env
from dotenv import load_dotenv
load_dotenv(backend.parent / ".env")

# Import after path is set
try:
    from src.agents.supervisor import super_graph
    
    print("=" * 60)
    print("Supervisor Graph Visualization")
    print("=" * 60)
    
    graph = super_graph.get_graph()
    
    print("\n📊 Nodes:")
    print("-" * 60)
    for node_name in graph.nodes.keys():
        print(f"  • {node_name}")
    
    print("\n🔗 Edges:")
    print("-" * 60)
    for edge in graph.edges:
        print(f"  {edge.source} → {edge.target}")
    
    print("\n📈 Mermaid Diagram:")
    print("-" * 60)
    mermaid = graph.draw_mermaid()
    print(mermaid)
    
    print("\n" + "=" * 60)
    print("💡 Copy the Mermaid diagram to https://mermaid.live/ to visualize!")
    print("=" * 60)
    
except Exception as e:
    print(f"Error: {e}")
    print("\nTry running from the notebook instead: backend/visualize_graph.ipynb")

