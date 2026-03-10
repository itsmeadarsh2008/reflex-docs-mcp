# Reflex Docs MCP Server

> **Version 0.2.0** — 14 tools, connection pooling, FTS5 query upgrades, TTL caching

## New in 0.2.0

### New Tools
- **`get_code_examples(topic)`** — Find Python code examples from docs for a topic
- **`decode_error(error_text)`** — Analyze a Reflex error and find relevant docs
- **`get_changelog(version?)`** — Fetch Reflex release notes from GitHub
- **`get_migration_guide(from_version, to_version)`** — Get migration guidance between versions
- **`search_api_reference(symbol)`** — Look up API reference for a Reflex symbol
- **`get_component_props(name)`** — Get only the props table for a component
- **`list_recipes(category?)`** — Browse recipe/tutorial pages

### Enhancements
- **`search_docs`** — New `fuzzy` flag (prefix expansion), `include_content` flag (full page content)
- **`get_doc`** — New `extract_code` flag (return only fenced code blocks)

### Performance
- SQLite connection pooling via `threading.local()` with persistent per-thread connections
- WAL journal mode, 64 MB page cache, 256 MB mmap for concurrent reads
- LRU cache (512 entries) on slug lookups
- In-process TTL cache (300s default) on search results
- FTS5 query preprocessor: phrase match + prefix expansion
- Incremental indexing — skips re-index if git commit unchanged

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
- `search_docs(query, limit?, include_content?, fuzzy?)` — Full-text search with fuzzy matching
- `get_doc(slug, extract_code?)` — Retrieve a full doc page by slug
- `list_pages(prefix?, limit?)` — List doc pages by slug prefix
- `list_components(category?)` — List all Reflex components
- `search_components(query, limit?)` — Search components by name/description
- `get_component(name)` — Get details about a specific component
- `get_component_props(name, filter?)` — Get component props table
- `get_stats()` — Database statistics
- `get_code_examples(topic, limit?)` — Find Python code examples for a topic
- `decode_error(error_text, context?)` — Analyze errors against docs
- `get_changelog(version?, limit?)` — Fetch Reflex release notes
- `get_migration_guide(from_version, to_version)` — Migration guidance between versions
- `search_api_reference(symbol)` — API reference lookup
- `list_recipes(category?)` — Browse recipe/tutorial pages

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
│   ├── http.py            # Shared HTTP client with TTL cache
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
- `REFLEX_DOCS_CACHE_TTL` (default: 300) — Seconds for search cache TTL
- `REFLEX_DOCS_HTTP_TIMEOUT` (default: 10) — Seconds for outbound HTTP requests
- `REFLEX_DOCS_MAX_SEARCH_LIMIT` (default: 30) — Hard cap on search result limit
- `REFLEX_DOCS_ENABLE_LIVE_FETCH` (default: true) — If false, disable live HTTP fetches

## License
MIT
