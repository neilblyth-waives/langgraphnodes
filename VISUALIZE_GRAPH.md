# Visualize Supervisor Graph

## Quick Method (Option 3)

Run this command from the project root:

```bash
cd backend
python visualize_graph.py
```

Or run directly in Python:

```bash
cd backend
python -c "import sys; sys.path.insert(0, 'src'); from agents.supervisor import super_graph; print(super_graph.get_graph().draw_mermaid())"
```

## Interactive Python

You can also run it interactively:

```bash
cd backend
python
```

Then in Python:

```python
import sys
sys.path.insert(0, 'src')
from agents.supervisor import super_graph

# Get Mermaid diagram
graph = super_graph.get_graph()
mermaid = graph.draw_mermaid()
print(mermaid)

# Copy the output to https://mermaid.live/ to visualize
```

## What You'll See

The script will output:
1. **Mermaid diagram code** - Copy this to https://mermaid.live/ for visual graph
2. **Graph nodes** - List of all nodes (supervisor, budget, performance)
3. **Graph edges** - How nodes connect (START → supervisor → budget/performance → supervisor → END)

## Visualize Online

1. Copy the Mermaid diagram output
2. Go to https://mermaid.live/
3. Paste the diagram
4. See your graph visualization!

