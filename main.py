"""Entry point for the Reflex Docs MCP Server."""

import logging

from reflex_docs_mcp.bootstrap import ensure_index, env_flag
from reflex_docs_mcp.server import mcp, main as run_main

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# FastMCP hosting expects a top-level server object named
# mcp/server/app. We export mcp and alias app for compatibility.
app = mcp

if __name__ == "__main__":
    if env_flag("REFLEX_DOCS_AUTO_INDEX", True):
        ensure_index()
    run_main()
