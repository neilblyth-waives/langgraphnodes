# Dependency Visualization Guide

Generated: 2026-01-14

This folder contains dependency visualizations created with `pydeps` to help understand the project structure.

---

## Generated Files

### 1. `architecture_dependencies.svg` (Main View)
**Command**: `pydeps backend/src --max-bacon=3 --cluster`

**What it shows**:
- Complete dependency graph with clustering
- Shows how modules are grouped together (agents, tools, api, core, memory)
- Includes up to 3 levels of import depth
- Arrows show import relationships (A → B means "A imports B")

**Best for**: Understanding the complete structure and relationships

---

### 2. `architecture_simple.svg` (Simplified View)
**Command**: `pydeps backend/src --max-bacon=2`

**What it shows**:
- Simpler view with only 2 levels of depth
- Less cluttered, easier to read
- Focus on main module relationships

**Best for**: Quick overview without too much detail

---

### 3. `architecture_high_level.svg` (Module Overview)
**Command**: `pydeps backend/src --max-bacon=1 --only src`

**What it shows**:
- Highest level view
- Only shows main src-level modules
- Clearest view of architectural layers

**Best for**: Understanding high-level architecture at a glance

---

## How to Read the Diagrams

### Node Colors
- **Green**: Entry points / main modules
- **Blue**: Regular modules
- **Red**: External dependencies (not from your code)

### Arrows
- **Solid arrow (→)**: Direct import relationship
- Direction shows "imports from" relationship
  - `api.chat → agents.conductor` means "chat imports conductor"

### Clusters (boxes)
Groups related modules together by their package structure:
- `agents` cluster: All agent modules
- `tools` cluster: All tool modules
- `api` cluster: API routes and endpoints
- `core` cluster: Configuration, database, cache
- `memory` cluster: Session and memory management
- `schemas` cluster: Pydantic data models

---

## Key Insights from the Graphs

### Architectural Layers (Top to Bottom)
1. **API Layer** (`api/`)
   - Entry point for user requests
   - Imports from agents and memory

2. **Agent Layer** (`agents/`)
   - Business logic and orchestration
   - Imports from tools and memory

3. **Tools Layer** (`tools/`)
   - Specific functionality (Snowflake, memory, logging)
   - Imports from core utilities

4. **Core Layer** (`core/`)
   - Configuration, database, cache, telemetry
   - Foundation layer, imported by everything

5. **Memory Layer** (`memory/`)
   - Session and vector store management
   - Uses core for database access

6. **Schemas Layer** (`schemas/`)
   - Data models (Pydantic)
   - Used across all layers for type safety

### Important Dependencies
- **API routes depend on**: Conductor agent, session manager
- **Conductor depends on**: All specialist agents, memory tool
- **All agents depend on**: Base agent, tools, memory
- **All tools depend on**: Core configuration and logging
- **Memory depends on**: Database, cache, embeddings

---

## Viewing the Files

### In a Browser
```bash
open docs/architecture_dependencies.svg
```

### In VS Code
- Install "SVG" extension
- Right-click SVG file → "Open Preview"

### Convert to PNG (if needed)
```bash
brew install imagemagick
convert docs/architecture_dependencies.svg docs/architecture_dependencies.png
```

---

## Updating the Diagrams

When you add/modify files, regenerate:

```bash
# Main view with clustering
pydeps backend/src --max-bacon=3 --cluster -o docs/architecture_dependencies.svg

# Simple view
pydeps backend/src --max-bacon=2 -o docs/architecture_simple.svg

# High-level view
pydeps backend/src --max-bacon=1 --only src -o docs/architecture_high_level.svg
```

---

## Next Steps

For detailed understanding of what each file DOES (not just imports):
- See `FILE_REFERENCE.md` (to be created)
- See `ARCHITECTURE.md` for architecture explanation
- See `DATA_FLOW.md` for request flow diagrams

For runtime behavior (what actually executes):
- Use `pycallgraph2` to trace a real request
- Use `snakeviz` to profile performance

---

## Troubleshooting

**Graphs are too cluttered:**
- Use lower `--max-bacon` value (1 or 2)
- Add `--only src` to filter out external deps
- Focus on specific module: `pydeps backend/src/agents`

**Missing modules:**
- Make sure all `__init__.py` files exist
- Check for import errors: `python -m backend.src`

**Want interactive exploration:**
- Consider using `pydeps --show` (opens in browser with zoom)
- Or convert to interactive HTML with D3.js visualization
