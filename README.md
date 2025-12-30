# Reflex Docs MCP Server

**Give your LLMs a "Photographic Memory" of the Reflex Documentation.**

This Project is an **Model Context Protocol (MCP) Server** designed to ground AI agents in the actual, latest documentation of the [Reflex](https://reflex.dev/) web framework. 

### Why this exists?
LLMs often hallucinate parameters or use outdated syntax when writing Reflex code. This server solves that by exposing the valid, up-to-date documentation as **tools** that the LLM can call on-demand.

Instead of guessing, the AI works like a developer:
1.  **Searches** the docs for a component (e.g., `search_docs("rx.foreach")`).
2.  **Reads** the specific page (`get_doc("library/dynamic-rendering/foreach")`).
3.  **Inspects** component schemas (`get_component("rx.button")`).
4.  **Writes** accurate, working code based on the ground truth.

---

## Features

- **Full-text search** over Reflex docs using SQLite FTS5 (blazing fast <2ms response)
- **Section-level retrieval** to give LLMs just the context they need (saving tokens)
- **Component index** allowing lookups of properties and categories for every `rx.*` component
- **Deployable API** via FastAPI, ready for Render/Railway/Vercel
- **Zero-Hallucination Workflow** when integrated into an agentic loop

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Health check |
| `GET /search?query=...&limit=10` | Search docs |
| `GET /doc/{slug}` | Get full page |
| `GET /components?category=...` | List components |
| `GET /component/{name}` | Get component info |
| `GET /stats` | Database statistics |

## Local Development

```bash
# Clone and install
git clone https://github.com/yourusername/reflex-docs-mcp.git
cd reflex-docs-mcp
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -e .

# Index the docs (downloads Reflex docs and builds search index)
python -m src.reflex_docs_mcp.indexer

# Run the API server
python api.py
# Open http://localhost:8000
```

## Deployment to Render

### Option 1: One-Click Deploy
1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → New → Web Service
3. Connect your GitHub repo
4. Render will auto-detect settings from `render.yaml`
5. Deploy!

### Option 2: Manual Setup
1. **Build Command**: 
   ```bash
   pip install -e . && python -m src.reflex_docs_mcp.indexer
   ```
2. **Start Command**: 
   ```bash
   uvicorn api:app --host 0.0.0.0 --port $PORT
   ```

### Environment Variables
- `PORT` - Set automatically by Render

## Project Structure

```
├── api.py                  # FastAPI server (deploy this)
├── main.py                 # MCP stdio entry point
├── src/reflex_docs_mcp/
│   ├── models.py           # Pydantic data models
│   ├── database.py         # SQLite + FTS5 operations
│   ├── parser.py           # Markdown parser
│   ├── indexer.py          # Docs cloning & indexing
│   └── server.py           # MCP server (stdio)
├── render.yaml             # Render deployment config
├── Procfile                # Process definition
└── test.py                 # Groq + MCP agentic demo
```

## Using with Groq/LLMs

See `test.py` for an example of using this MCP server with Groq's API in an agentic loop:

```python
# The model calls search_docs → gets results → provides answer
python test.py
```

## MCP Tools (for stdio mode)

| Tool | Description |
|------|-------------|
| `search_docs(query)` | Full-text search over Reflex docs |
| `get_doc(slug)` | Retrieve a full doc page by slug |
| `list_components(category?)` | List all documented Reflex components |
| `get_component(name)` | Get info for a specific component |

## License

MIT
