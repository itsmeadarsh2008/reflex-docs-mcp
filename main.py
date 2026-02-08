"""Entry point for the Reflex Docs MCP Server."""

import logging
import os
from pathlib import Path

from reflex_docs_mcp import database, indexer
from reflex_docs_mcp.server import mcp, main as run_main, check_database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# FastMCP hosting expects a top-level server object named
# mcp/server/app. We export mcp and alias app for compatibility.
app = mcp

def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def ensure_index() -> None:
    """Ensure the docs index exists; build it if missing."""
    database.init_db()
    if check_database():
        return

    docs_src = Path(os.getenv("REFLEX_DOCS_DOCS_SRC", str(indexer.DEFAULT_DOCS_SRC)))
    force_clone = _env_flag("REFLEX_DOCS_FORCE_CLONE", False)
    skip_clone = _env_flag("REFLEX_DOCS_SKIP_CLONE", False)
    keep_existing = _env_flag("REFLEX_DOCS_KEEP_EXISTING", False)

    logger.warning("Documentation index missing; building it now...")

    if skip_clone:
        docs_dir = docs_src / "docs"
        if not docs_dir.exists():
            raise RuntimeError(f"Docs directory not found: {docs_dir}")
    else:
        docs_dir = indexer.clone_or_update_docs(docs_src, force_clone=force_clone)

    indexer.index_docs(docs_dir, clear_existing=not keep_existing)


# Run indexing programmatically on startup (can be disabled)
if _env_flag("REFLEX_DOCS_AUTO_INDEX", True):
    ensure_index()

if __name__ == "__main__":
    run_main()
