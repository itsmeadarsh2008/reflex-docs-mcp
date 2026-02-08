# Reflex Docs MCP Server

Ground AI agents in real, up-to-date Reflex docs via a fast, local MCP server.

**Python:** 3.14 recommended. Compatible with 3.13+.

## What It Does
- Full‑text search over Reflex docs (SQLite FTS5)
- Section‑level retrieval for precise context
- Component index for `rx.*` lookups
- FastMCP server with stdio and SSE transports

## Quickstart

```bash
# Create venv
python3.14 -m venv .venv
. .venv/bin/activate

# Install
pip install -e .

# Index docs (clones Reflex docs and builds search index)
python -m reflex_docs_mcp.indexer

# Run MCP server (stdio)
python -m reflex_docs_mcp.server

# Run MCP server over SSE
python -m reflex_docs_mcp.server --transport sse --host 127.0.0.1 --port 8000
```

## MCP Tools
- `search_docs(query)`
- `get_doc(slug)`
- `list_pages(prefix?, limit?)`
- `list_components(category?)`
- `search_components(query, limit?)`
- `get_component(name)`
- `get_stats()`

## Local MCP Config (VS Code)
The repository includes a ready-to-use config at `.vscode/mcp.json` that runs the server with the local venv.

## Project Layout
```
├── main.py                 # MCP stdio entry point
├── src/reflex_docs_mcp/
│   ├── models.py           # Pydantic data models
│   ├── database.py         # SQLite + FTS5 operations
│   ├── parser.py           # Markdown parser
│   ├── indexer.py          # Docs cloning & indexing
│   └── server.py           # MCP server (stdio + SSE)
├── render.yaml             # Render deployment config
├── Procfile                # Process definition
└── test.py                 # OpenRouter + MCP demo client
```

## Demo (Optional)
The demo client uses Groq (OpenAI-compatible API) and the MCP Python client.

```bash
pip install -e ".[demo]"
cp env.example .env
# Add GROQ_API_KEY to .env
python test.py
```

## Notes
- `env.example` contains Groq settings.
- The indexer writes to `data/reflex_docs.db` by default.
