"""Indexer script to clone Reflex docs and build the search index."""

import logging
import shutil
from pathlib import Path

try:
    import git

    HAS_GIT = True
except ImportError:
    HAS_GIT = False

from . import database
from .parser import (
    parse_doc_file,
    extract_component_description,
    get_category_from_slug,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Repository URL and paths
REFLEX_WEB_REPO = "https://github.com/reflex-dev/reflex-web.git"
DEFAULT_DOCS_SRC = Path(__file__).parent.parent.parent / "docs_src"


def clone_or_update_docs(
    docs_src: Path = DEFAULT_DOCS_SRC, force_clone: bool = False
) -> Path:
    """Clone or update the Reflex docs repository.

    Args:
        docs_src: Directory to clone into
        force_clone: If True, remove existing and clone fresh

    Returns:
        Path to the docs directory (docs_src/docs)
    """
    if not HAS_GIT:
        raise ImportError(
            "GitPython is required for cloning. Install with: pip install gitpython"
        )

    if force_clone and docs_src.exists():
        logger.info(f"Removing existing docs at {docs_src}")
        shutil.rmtree(docs_src)

    if docs_src.exists():
        logger.info(f"Updating existing docs at {docs_src}")
        try:
            repo = git.Repo(docs_src)
            origin = repo.remote("origin")
            origin.pull()
            logger.info("Docs updated successfully")
        except git.GitCommandError as e:
            logger.warning(f"Failed to update docs: {e}")
            logger.info("Continuing with existing docs")
    else:
        logger.info(f"Cloning Reflex docs to {docs_src}")
        # Shallow clone for faster download
        git.Repo.clone_from(
            REFLEX_WEB_REPO, docs_src, depth=1, single_branch=True, branch="main"
        )
        logger.info("Docs cloned successfully")

    return docs_src / "docs"


def index_docs(docs_dir: Path, clear_existing: bool = True) -> dict:
    """Index all documentation files into the database.

    Args:
        docs_dir: Path to the docs directory
        clear_existing: If True, clear database before indexing

    Returns:
        Statistics about the indexing operation
    """
    logger.info(f"Indexing docs from {docs_dir}")

    # Initialize and optionally clear database
    database.init_db()
    if clear_existing:
        logger.info("Clearing existing index")
        database.clear_db()

    stats = {
        "files_processed": 0,
        "sections_indexed": 0,
        "components_indexed": 0,
        "errors": 0,
    }

    # Find all markdown files
    md_files = list(docs_dir.rglob("*.md"))
    logger.info(f"Found {len(md_files)} markdown files")

    sections_batch: list[tuple[str, str, str, int, str, int, str]] = []
    components_batch: list[tuple[str, str | None, str, str | None, str | None]] = []
    batch_size = 1000

    with database.transaction() as conn:
        for file_path in md_files:
            try:
                # Skip __init__.py and non-doc files
                if file_path.name.startswith("_"):
                    continue

                # Parse the file
                parsed = parse_doc_file(file_path, docs_dir)

                # Collect sections
                for section in parsed.sections:
                    sections_batch.append(
                        (
                            parsed.slug,
                            parsed.title,
                            section.heading,
                            section.level,
                            section.content,
                            section.position,
                            parsed.url,
                        )
                    )

                # Collect components from frontmatter
                for component_name in parsed.components:
                    # Ensure rx. prefix
                    if not component_name.startswith("rx."):
                        component_name = f"rx.{component_name}"

                    category = get_category_from_slug(parsed.slug)
                    description = extract_component_description(parsed)

                    components_batch.append(
                        (component_name, category, description, parsed.slug, parsed.url)
                    )

                # Flush batches
                if len(sections_batch) >= batch_size:
                    stats["sections_indexed"] += database.insert_sections_many(
                        sections_batch, conn=conn
                    )
                    sections_batch.clear()

                if len(components_batch) >= batch_size:
                    stats["components_indexed"] += database.insert_components_many(
                        components_batch, conn=conn
                    )
                    components_batch.clear()

                stats["files_processed"] += 1

                if stats["files_processed"] % 50 == 0:
                    logger.info(f"Processed {stats['files_processed']} files...")

            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
                stats["errors"] += 1

        # Final flush
        if sections_batch:
            stats["sections_indexed"] += database.insert_sections_many(
                sections_batch, conn=conn
            )
            sections_batch.clear()
        if components_batch:
            stats["components_indexed"] += database.insert_components_many(
                components_batch, conn=conn
            )
            components_batch.clear()

    logger.info(f"Indexing complete: {stats}")
    return stats


def main():
    """Main entry point for the indexer CLI."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Index Reflex documentation for the MCP server"
    )
    parser.add_argument(
        "--docs-src",
        type=Path,
        default=DEFAULT_DOCS_SRC,
        help="Directory to clone/store docs",
    )
    parser.add_argument(
        "--force-clone", action="store_true", help="Force fresh clone of docs repo"
    )
    parser.add_argument(
        "--skip-clone", action="store_true", help="Skip cloning, use existing docs"
    )
    parser.add_argument(
        "--keep-existing", action="store_true", help="Keep existing index entries"
    )

    args = parser.parse_args()

    # Clone or update docs
    if args.skip_clone:
        docs_dir = args.docs_src / "docs"
        if not docs_dir.exists():
            logger.error(f"Docs directory not found: {docs_dir}")
            logger.error("Run without --skip-clone to clone the docs first")
            return 1
    else:
        docs_dir = clone_or_update_docs(args.docs_src, args.force_clone)

    # Index the docs
    stats = index_docs(docs_dir, clear_existing=not args.keep_existing)

    # Print summary
    print("\n" + "=" * 50)
    print("Indexing Summary")
    print("=" * 50)
    print(f"Files processed: {stats['files_processed']}")
    print(f"Sections indexed: {stats['sections_indexed']}")
    print(f"Components indexed: {stats['components_indexed']}")
    print(f"Errors: {stats['errors']}")
    print("=" * 50)

    # Print database stats
    db_stats = database.get_stats()
    print("\nDatabase contains:")
    print(f"  - {db_stats['pages']} documentation pages")
    print(f"  - {db_stats['sections']} searchable sections")
    print(f"  - {db_stats['components']} components")

    return 0


if __name__ == "__main__":
    exit(main())
