"""Entry point for the Reflex Docs MCP Server."""

from reflex_docs_mcp.server import mcp, main as run_main

# FastMCP hosting expects a top-level server object named
# mcp/server/app. We export mcp and alias app for compatibility.
app = mcp

if __name__ == "__main__":
    run_main()
