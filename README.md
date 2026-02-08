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

# Install (local checkout)
pip install -e .

# Index docs (clones Reflex docs and builds search index)
python -m reflex_docs_mcp.indexer

# Run MCP server (stdio)
python -m reflex_docs_mcp.server

# Run MCP server over SSE
python -m reflex_docs_mcp.server --transport sse --host 127.0.0.1 --port 8000
```

## Install From PyPI

```bash
pip install reflex-docs-mcp
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

## Global Install MCP Config (VS Code)
If you install the package globally with `pip`, use one of these in `.vscode/mcp.json`:

Using module invocation:
```json
{
  "servers": {
    "reflex-docs": {
      "type": "stdio",
      "command": "python3",
      "args": ["-m", "reflex_docs_mcp.server"],
      "env": {
        "REFLEX_DOCS_AUTO_INDEX": "true"
      }
    }
  },
  "inputs": []
}
```

Using the CLI entry point:
```json
{
  "servers": {
    "reflex-docs": {
      "type": "stdio",
      "command": "reflex-docs-mcp",
      "args": [],
      "env": {
        "REFLEX_DOCS_AUTO_INDEX": "true"
      }
    }
  },
  "inputs": []
}
```

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
└── test.py                 # Groq + MCP demo client
```

## Demo (Optional)
The demo client uses Groq (OpenAI-compatible API) and the MCP Python client.

```bash
pip install reflex-docs-mcp[demo]
cp env.example .env
# Add GROQ_API_KEY to .env
python test.py
```

## Notes
- `env.example` contains Groq settings.
- The indexer writes to `data/reflex_docs.db` by default.
- On startup, the server auto-builds the index if missing. Controls:
- `REFLEX_DOCS_AUTO_INDEX` (default: true)
- `REFLEX_DOCS_DOCS_SRC` (path to clone docs into, default: `docs_src`)
- `REFLEX_DOCS_SKIP_CLONE` / `REFLEX_DOCS_FORCE_CLONE`
- `REFLEX_DOCS_KEEP_EXISTING`

## License
MIT
