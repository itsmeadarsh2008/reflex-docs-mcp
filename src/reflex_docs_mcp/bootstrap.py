"""Startup helpers for indexing and configuration."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from . import database, indexer

logger = logging.getLogger(__name__)


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def ensure_index() -> None:
    """Ensure the docs index exists; build it if missing."""
    database.init_db()
    if database.is_index_ready():
        return

    docs_src = Path(os.getenv("REFLEX_DOCS_DOCS_SRC", str(indexer.DEFAULT_DOCS_SRC)))
    force_clone = env_flag("REFLEX_DOCS_FORCE_CLONE", False)
    skip_clone = env_flag("REFLEX_DOCS_SKIP_CLONE", False)
    keep_existing = env_flag("REFLEX_DOCS_KEEP_EXISTING", False)

    logger.warning("Documentation index missing; building it now...")

    if skip_clone:
        docs_dir = docs_src / "docs"
        if not docs_dir.exists():
            raise RuntimeError(f"Docs directory not found: {docs_dir}")
    else:
        docs_dir = indexer.clone_or_update_docs(docs_src, force_clone=force_clone)

    indexer.index_docs(docs_dir, clear_existing=not keep_existing)
