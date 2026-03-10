"""FastMCP server exposing Reflex documentation tools."""

import logging
import os
import re
from contextlib import asynccontextmanager

import anyio
from fastmcp import FastMCP

from . import database
from .bootstrap import ensure_index, env_flag
from .http import fetch

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Reasonable hard limits to protect the server from huge responses.
_MAX_SEARCH_RESULTS = int(os.getenv("REFLEX_DOCS_MAX_SEARCH_LIMIT", "30"))
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
    - search_docs: Search the documentation using keywords (supports fuzzy search)
    - get_doc: Get a full documentation page by its slug (supports code extraction)
    - list_pages: List documentation pages by slug prefix
    - list_components: List all Reflex components
    - search_components: Search components by name or description
    - get_component: Get details about a specific component
    - get_component_props: Get only the props table for a component
    - get_stats: Get database statistics
    - get_code_examples: Find Python code examples for a topic
    - decode_error: Analyze a Reflex error and find relevant docs
    - get_changelog: Fetch Reflex release notes
    - get_migration_guide: Get migration guidance between versions
    - search_api_reference: Look up API reference for a symbol
    - list_recipes: Browse recipe/tutorial pages
    """,
    lifespan=lifespan,
)


@mcp.tool
def search_docs(
    query: str,
    limit: int = 10,
    include_content: bool = False,
    fuzzy: bool = True,
) -> list[dict]:
    """Search Reflex documentation by keyword or natural language query.

    Args:
        query: Search query (e.g., "rx.foreach", "state management", "styling")
        limit: Maximum number of results to return (default: 10)
        include_content: If True, include full page content in each result (max 5 results)
        fuzzy: If True, enable prefix expansion for broader matching (default: True)

    Returns:
        List of matching documentation sections with slug, title, score, snippet, and URL

    Example:
        search_docs("rx.foreach")
        search_docs("how to style components", fuzzy=True)
    """
    limit = max(1, min(limit, _MAX_SEARCH_RESULTS))
    if include_content:
        limit = min(limit, 5)
    logger.info(f"Searching docs: {query} (limit={limit}, fuzzy={fuzzy})")

    try:
        results = database.search_sections(query, limit=limit, fuzzy=fuzzy)
        out = [result.model_dump() for result in results]
        if include_content:
            for item in out:
                page = database.get_page_sections_cached(item["slug"])
                if page:
                    item["content"] = "\n\n".join(
                        s.content for s in page.sections
                    )
        return out
    except Exception as e:
        logger.error(f"Search error: {e}")
        return []


@mcp.tool
def get_doc(slug: str, extract_code: bool = False) -> dict | None:
    """Retrieve a full documentation page by its slug.

    Args:
        slug: Document slug (e.g., "library/layout/box", "components/rendering_iterables")
        extract_code: If True, return only fenced code blocks from the page

    Returns:
        Full document with title, URL, and all sections with markdown content

    Example:
        get_doc("library/layout/box")
        get_doc("state/overview", extract_code=True)
    """
    logger.info(f"Getting doc: {slug}")

    try:
        page = database.get_page_sections_cached(slug)
        if not page:
            return None
        result = page.model_dump()
        if extract_code:
            full_content = "\n\n".join(s.content for s in page.sections)
            result["code_blocks"] = re.findall(
                r"```\w*\n(.*?)```", full_content, re.DOTALL
            )
        return result
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


@mcp.tool
def get_code_examples(topic: str, limit: int = 5) -> dict:
    """Find Python code examples from Reflex docs related to a topic.

    Args:
        topic: Topic to search for (e.g., "state vars", "event handlers")
        limit: Maximum number of code examples to return (default: 5)

    Returns:
        Dict with topic, count, and list of code examples with source info
    """
    logger.info(f"Getting code examples: {topic} (limit={limit})")
    try:
        results = database.search_sections(topic, limit=20)
        topic_tokens = topic.lower().split()
        examples: list[dict] = []
        for result in results:
            page = database.get_page_sections_cached(result.slug)
            if not page:
                continue
            full_content = "\n\n".join(s.content for s in page.sections)
            blocks = re.findall(r"```python\n(.*?)```", full_content, re.DOTALL)
            for block in blocks:
                # Find position of the block in full_content
                idx = full_content.find(f"```python\n{block}```")
                if idx == -1:
                    continue
                context = full_content[max(0, idx - 200) : idx].lower()
                if any(t in context for t in topic_tokens):
                    examples.append(
                        {
                            "source_slug": result.slug,
                            "source_title": result.title,
                            "code": block.strip(),
                        }
                    )
                    if len(examples) >= limit:
                        break
            if len(examples) >= limit:
                break
        return {"topic": topic, "count": len(examples), "examples": examples}
    except Exception as e:
        logger.error(f"Get code examples error: {e}")
        return {"topic": topic, "count": 0, "examples": [], "error": str(e)}


@mcp.tool
def decode_error(error_text: str, context: str = "") -> dict:
    """Analyze a Reflex error and find relevant documentation.

    Args:
        error_text: The error message or traceback text
        context: Optional additional context about what you were doing

    Returns:
        Dict with error class, rx symbols, relevant docs, and search queries used
    """
    logger.info(f"Decoding error: {error_text[:80]}...")
    try:
        # Extract exception class
        match = re.search(r"(\w+Error|\w+Exception|\w+Warning)", error_text)
        error_class = match.group(1) if match else None

        # Extract rx.* symbols
        rx_symbols = re.findall(r"rx\.\w+", error_text)

        queries_used = []
        all_results: list[dict] = []
        seen_slugs: set[str] = set()

        # Search with truncated error text
        q1 = error_text[:120]
        queries_used.append(q1)
        results1 = database.search_sections(q1, limit=8)
        for r in results1:
            if r.slug not in seen_slugs:
                seen_slugs.add(r.slug)
                all_results.append(
                    {"slug": r.slug, "title": r.title, "snippet": r.snippet}
                )

        # Search with exception class name
        if error_class:
            queries_used.append(error_class)
            results2 = database.search_sections(error_class, limit=5)
            for r in results2:
                if r.slug not in seen_slugs:
                    seen_slugs.add(r.slug)
                    all_results.append(
                        {"slug": r.slug, "title": r.title, "snippet": r.snippet}
                    )

        return {
            "error_class": error_class,
            "rx_symbols": rx_symbols,
            "relevant_docs": all_results,
            "search_queries_used": queries_used,
        }
    except Exception as e:
        logger.error(f"Decode error error: {e}")
        return {
            "error_class": None,
            "rx_symbols": [],
            "relevant_docs": [],
            "search_queries_used": [],
            "error": str(e),
        }


@mcp.tool
def get_changelog(version: str = "", limit: int = 5) -> dict:
    """Fetch Reflex release notes from the changelog.

    Args:
        version: Specific version to fetch (e.g., "0.6.1"). Empty for latest releases.
        limit: Number of recent releases to return if version is empty (default: 5)

    Returns:
        Dict with requested version, count, source URL, and release sections
    """
    logger.info(f"Getting changelog: version={version!r}, limit={limit}")
    source_url = "https://raw.githubusercontent.com/reflex-dev/reflex/main/CHANGELOG.md"
    try:
        text = fetch(source_url, ttl=3600)
        if not text:
            return {
                "requested_version": version,
                "returned_count": 0,
                "source": source_url,
                "releases": [],
                "error": "Failed to fetch changelog",
            }

        # Parse into sections by ## headings
        sections = re.split(r"\n(?=## )", text)
        releases: list[dict] = []
        for section in sections:
            heading_match = re.match(r"## \[?(\d+\.\d+\.\d+[^\]]*)\]?", section)
            if not heading_match:
                continue
            ver = heading_match.group(1).strip()
            # Try to extract date
            date_match = re.search(r"\d{4}-\d{2}-\d{2}", section[:200])
            date = date_match.group(0) if date_match else ""
            content = section[heading_match.end() :].strip()
            releases.append({"version": ver, "date": date, "content": content})

        if version:
            releases = [r for r in releases if r["version"].startswith(version)]

        releases = releases[:limit]
        return {
            "requested_version": version,
            "returned_count": len(releases),
            "source": source_url,
            "releases": releases,
        }
    except Exception as e:
        logger.error(f"Get changelog error: {e}")
        return {
            "requested_version": version,
            "returned_count": 0,
            "source": source_url,
            "releases": [],
            "error": str(e),
        }


@mcp.tool
def get_migration_guide(from_version: str, to_version: str) -> dict:
    """Get migration guidance between two Reflex versions.

    Args:
        from_version: The version you're migrating from (e.g., "0.5.0")
        to_version: The version you're migrating to (e.g., "0.6.0")

    Returns:
        Dict with breaking changes, relevant docs, and changelog section
    """
    logger.info(f"Getting migration guide: {from_version} -> {to_version}")
    try:
        changelog = get_changelog(version=to_version, limit=1)
        changelog_section = ""
        breaking_changes: list[str] = []

        if changelog.get("releases"):
            release = changelog["releases"][0]
            changelog_section = release.get("content", "")
            # Extract breaking changes
            for line in changelog_section.splitlines():
                stripped = line.strip()
                if any(
                    stripped.startswith(prefix)
                    for prefix in ("**Breaking**", "### Breaking", "⚠️")
                ):
                    breaking_changes.append(stripped)

        # Search docs for migration-related content
        search_queries = [
            f"migration {from_version}",
            f"upgrade {to_version}",
            "breaking changes",
        ]
        relevant_docs: list[dict] = []
        seen_slugs: set[str] = set()
        for q in search_queries:
            try:
                results = database.search_sections(q, limit=3)
                for r in results:
                    if r.slug not in seen_slugs:
                        seen_slugs.add(r.slug)
                        relevant_docs.append(
                            {"slug": r.slug, "title": r.title, "snippet": r.snippet}
                        )
            except Exception:
                pass

        return {
            "from_version": from_version,
            "to_version": to_version,
            "breaking_changes": breaking_changes,
            "relevant_docs": relevant_docs,
            "changelog_section": changelog_section,
        }
    except Exception as e:
        logger.error(f"Get migration guide error: {e}")
        return {
            "from_version": from_version,
            "to_version": to_version,
            "breaking_changes": [],
            "relevant_docs": [],
            "changelog_section": "",
            "error": str(e),
        }


@mcp.tool
def search_api_reference(symbol: str) -> dict:
    """Look up API reference documentation for a Reflex symbol.

    Args:
        symbol: The symbol to look up (e.g., "rx.State", "rx.button", "EventHandler")

    Returns:
        Dict with symbol info, headings, code blocks, and tables
    """
    logger.info(f"Searching API reference: {symbol}")
    slug = symbol.lower().replace(".", "-").replace("_", "-")
    url = f"https://reflex.dev/docs/api-reference/{slug}/"
    try:
        text = fetch(url, ttl=3600)
        if text:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(text, "html.parser")
            h1 = soup.find("h1")
            headings = [
                h.get_text(strip=True) for h in soup.find_all(["h2", "h3"])
            ]
            code_blocks = [
                pre.get_text() for pre in soup.find_all("pre")
            ]
            tables = [
                table.get_text(separator=" | ", strip=True)
                for table in soup.find_all("table")
            ]
            return {
                "symbol": symbol,
                "source": "live",
                "title": h1.get_text(strip=True) if h1 else symbol,
                "headings": headings,
                "code_blocks": code_blocks,
                "tables": tables,
            }

        # Fallback to indexed search
        results = database.search_sections(symbol, limit=5)
        return {
            "symbol": symbol,
            "source": "index_fallback",
            "headings": [r.title for r in results],
            "code_blocks": [],
            "tables": [],
        }
    except Exception as e:
        logger.error(f"Search API reference error: {e}")
        return {
            "symbol": symbol,
            "source": "error",
            "headings": [],
            "code_blocks": [],
            "tables": [],
            "error": str(e),
        }


@mcp.tool
def get_component_props(name: str, filter: str = "") -> dict:
    """Get the props table for a specific Reflex component.

    Args:
        name: Component name (e.g., "rx.button", "button"). The "rx." prefix is optional.
        filter: Optional filter string to match prop names or descriptions

    Returns:
        Dict with component name, total props count, and filtered props list
    """
    logger.info(f"Getting component props: {name} (filter={filter!r})")
    try:
        comp = database.get_component_by_name(name)
        if not comp:
            return {
                "component": name,
                "total_props": 0,
                "filtered_by": filter,
                "props": [],
                "error": f"Component '{name}' not found",
            }

        # Get the doc page for more detail
        page = database.get_page_sections_cached(comp.doc_slug) if comp.doc_slug else None
        props: list[dict] = []
        if page:
            full_content = "\n\n".join(s.content for s in page.sections)
            # Try to extract prop-like lines from tables or definitions
            # Look for markdown table rows with prop info
            for line in full_content.splitlines():
                if "|" in line and not line.strip().startswith("|--"):
                    cells = [c.strip() for c in line.split("|") if c.strip()]
                    if len(cells) >= 2 and cells[0] not in ("Prop", "Name", "---"):
                        prop = {"name": cells[0], "type": cells[1] if len(cells) > 1 else ""}
                        if len(cells) > 2:
                            prop["default"] = cells[2]
                        if len(cells) > 3:
                            prop["description"] = cells[3]
                        props.append(prop)

        total = len(props)
        if filter:
            filter_lower = filter.lower()
            props = [
                p
                for p in props
                if filter_lower in p.get("name", "").lower()
                or filter_lower in p.get("description", "").lower()
            ]

        return {
            "component": comp.name,
            "total_props": total,
            "filtered_by": filter,
            "props": props,
        }
    except Exception as e:
        logger.error(f"Get component props error: {e}")
        return {
            "component": name,
            "total_props": 0,
            "filtered_by": filter,
            "props": [],
            "error": str(e),
        }


@mcp.tool
def list_recipes(category: str = "") -> dict:
    """Browse recipe and tutorial pages from Reflex docs.

    Args:
        category: Optional category filter (e.g., "auth", "database")

    Returns:
        Dict with category filter, count, and list of recipes with summaries
    """
    logger.info(f"Listing recipes: category={category!r}")
    try:
        pages = database.list_pages(prefix="recipes")
        if category:
            pages = [p for p in pages if category.lower() in p.slug.lower()]

        recipes: list[dict] = []
        for p in pages:
            summary = ""
            page = database.get_page_sections_cached(p.slug)
            if page:
                for section in page.sections:
                    content = section.content.strip()
                    if content and not content.startswith("#"):
                        # First non-heading line
                        first_line = content.split("\n")[0].strip()
                        summary = first_line[:200]
                        break
            recipes.append({"slug": p.slug, "title": p.title, "summary": summary})

        return {
            "category_filter": category,
            "count": len(recipes),
            "recipes": recipes,
        }
    except Exception as e:
        logger.error(f"List recipes error: {e}")
        return {
            "category_filter": category,
            "count": 0,
            "recipes": [],
            "error": str(e),
        }


def main():
    """Main entry point for the MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="Run the Reflex Docs MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport protocol (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for SSE transport (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Port for SSE transport (default: 8000)"
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
