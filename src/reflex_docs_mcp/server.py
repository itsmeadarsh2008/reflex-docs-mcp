"""FastMCP server exposing Reflex documentation tools."""

import logging
from contextlib import asynccontextmanager

import anyio
from fastmcp import FastMCP

from . import database
from .bootstrap import ensure_index, env_flag

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Reasonable hard limits to protect the server from huge responses.
_MAX_SEARCH_RESULTS = 50
_MAX_PAGES_RESULTS = 500

@asynccontextmanager
async def lifespan(_server: FastMCP):
    if env_flag("REFLEX_DOCS_AUTO_INDEX", True):
        await anyio.to_thread.run_sync(ensure_index)
    yield {}


# Create the MCP server
mcp = FastMCP(
    "Reflex Docs MCP Server",
    instructions="""
    This server provides structured access to Reflex documentation.
    Use these tools to search and retrieve accurate, up-to-date information
    about Reflex components, state management, and best practices.
    
    Available tools:
    - search_docs: Search the documentation using keywords
    - get_doc: Get a full documentation page by its slug
    - list_pages: List documentation pages by slug prefix
    - list_components: List all Reflex components
    - search_components: Search components by name or description
    - get_component: Get details about a specific component
    - get_stats: Get database statistics
    """,
    lifespan=lifespan
)


@mcp.tool
def search_docs(query: str, limit: int = 10) -> list[dict]:
    """Search Reflex documentation by keyword or natural language query.
    
    Args:
        query: Search query (e.g., "rx.foreach", "state management", "styling")
        limit: Maximum number of results to return (default: 10)
    
    Returns:
        List of matching documentation sections with slug, title, score, snippet, and URL
    
    Example:
        search_docs("rx.foreach")
        search_docs("how to style components")
    """
    limit = max(1, min(limit, _MAX_SEARCH_RESULTS))
    logger.info(f"Searching docs: {query} (limit={limit})")
    
    try:
        results = database.search_sections(query, limit=limit)
        return [result.model_dump() for result in results]
    except Exception as e:
        logger.error(f"Search error: {e}")
        return []


@mcp.tool
def get_doc(slug: str) -> dict | None:
    """Retrieve a full documentation page by its slug.
    
    Args:
        slug: Document slug (e.g., "library/layout/box", "components/rendering_iterables")
    
    Returns:
        Full document with title, URL, and all sections with markdown content
    
    Example:
        get_doc("library/layout/box")
        get_doc("state/overview")
    """
    logger.info(f"Getting doc: {slug}")
    
    try:
        page = database.get_page_sections(slug)
        if page:
            return page.model_dump()
        return None
    except Exception as e:
        logger.error(f"Get doc error: {e}")
        return None


@mcp.tool
def list_components(category: str | None = None) -> list[dict]:
    """List all documented Reflex components.
    
    Args:
        category: Optional category filter (e.g., "layout", "forms", "data-display")
    
    Returns:
        List of components with name, category, description, and documentation URL
    
    Example:
        list_components()
        list_components("layout")
        list_components("forms")
    """
    logger.info(f"Listing components (category: {category})")
    
    try:
        components = database.list_all_components(category=category)
        return [comp.model_dump() for comp in components]
    except Exception as e:
        logger.error(f"List components error: {e}")
        return []


@mcp.tool
def search_components(query: str, limit: int = 20) -> list[dict]:
    """Search components by name or description.

    Args:
        query: Search query (e.g., "button", "layout", "table")
        limit: Maximum number of results to return (default: 20)

    Returns:
        List of matching components with name, category, description, and documentation URL
    """
    limit = max(1, min(limit, _MAX_SEARCH_RESULTS))
    logger.info(f"Searching components: {query} (limit={limit})")

    try:
        results = database.search_components(query, limit=limit)
        return [comp.model_dump() for comp in results]
    except Exception as e:
        logger.error(f"Search components error: {e}")
        return []


@mcp.tool
def get_component(name: str) -> dict | None:
    """Get detailed information about a specific Reflex component.
    
    Args:
        name: Component name (e.g., "rx.box", "rx.button", "box", "button")
              The "rx." prefix is optional.
    
    Returns:
        Component info with name, category, description, and documentation URL
    
    Example:
        get_component("rx.box")
        get_component("button")
    """
    logger.info(f"Getting component: {name}")
    
    try:
        component = database.get_component_by_name(name)
        if component:
            return component.model_dump()
        return None
    except Exception as e:
        logger.error(f"Get component error: {e}")
        return None


@mcp.tool
def list_pages(prefix: str | None = None, limit: int = 200) -> list[dict]:
    """List documentation pages, optionally filtered by slug prefix.

    Args:
        prefix: Optional slug prefix (e.g., "library/", "state/")
        limit: Maximum number of results to return (default: 200)

    Returns:
        List of pages with slug, title, and URL
    """
    limit = max(1, min(limit, _MAX_PAGES_RESULTS))
    logger.info(f"Listing pages (prefix: {prefix}, limit={limit})")

    try:
        pages = database.list_pages(prefix=prefix, limit=limit)
        return [page.model_dump() for page in pages]
    except Exception as e:
        logger.error(f"List pages error: {e}")
        return []


@mcp.tool
def get_stats() -> dict:
    """Get statistics about the indexed documentation.
    
    Returns:
        Dictionary with counts of pages, sections, and components
    """
    try:
        return database.get_stats()
    except Exception as e:
        logger.error(f"Get stats error: {e}")
        return {"error": str(e)}


def main():
    """Main entry point for the MCP server."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Run the Reflex Docs MCP Server"
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport protocol (default: stdio)"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for SSE transport (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for SSE transport (default: 8000)"
    )
    
    args = parser.parse_args()
    
    auto_index = env_flag("REFLEX_DOCS_AUTO_INDEX", True)
    if not auto_index and not database.is_index_ready():
        print("=" * 60)
        print("WARNING: Documentation index not found or empty!")
        print("Auto-indexing is disabled. Run the indexer:")
        print("  python -m reflex_docs_mcp.indexer")
        print("=" * 60)
        print()
    
    # Initialize database (creates tables if needed)
    database.init_db()
    
    # Run the server
    logger.info(f"Starting Reflex Docs MCP Server ({args.transport})")
    
    if args.transport == "stdio":
        mcp.run()
    else:
        mcp.run(transport="sse", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
