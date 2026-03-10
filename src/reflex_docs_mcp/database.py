"""SQLite database operations with FTS5 for full-text search."""

import atexit
import functools
import os
import re
import sqlite3
import threading
import time
from pathlib import Path
from contextlib import contextmanager, nullcontext
from typing import Generator, Iterable

from .models import DocResult, DocSection, DocPage, DocPageInfo, ComponentInfo

# Default database path
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "reflex_docs.db"

# Base URL for Reflex docs
REFLEX_DOCS_BASE_URL = "https://reflex.dev/docs"


def get_db_path() -> Path:
    """Get the database path, creating parent directories if needed."""
    db_path = DEFAULT_DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


_thread_local = threading.local()


def _apply_pragmas(conn: sqlite3.Connection) -> None:
    """Apply performance-related pragmas to the connection."""
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    # Negative cache_size means KB. -64000 ~= 64MB page cache.
    conn.execute("PRAGMA cache_size=-64000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA mmap_size=268435456")


def _get_thread_connection() -> sqlite3.Connection:
    """Get or create a per-thread SQLite connection."""
    conn = getattr(_thread_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(get_db_path(), timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        _apply_pragmas(conn)
        _thread_local.conn = conn
    return conn


def close_connection() -> None:
    """Close the current thread's connection, if any."""
    conn = getattr(_thread_local, "conn", None)
    if conn is not None:
        conn.close()
        _thread_local.conn = None


atexit.register(close_connection)


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """Get a cached database connection with row factory."""
    conn = _get_thread_connection()
    yield conn


@contextmanager
def transaction() -> Generator[sqlite3.Connection, None, None]:
    """Run operations inside a single transaction."""
    with get_connection() as conn:
        try:
            conn.execute("BEGIN")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def init_db() -> None:
    """Initialize the database with required tables."""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Main sections table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS docs_sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT NOT NULL,
                title TEXT NOT NULL,
                heading TEXT NOT NULL,
                level INTEGER NOT NULL,
                content TEXT NOT NULL,
                position INTEGER NOT NULL,
                url TEXT NOT NULL
            )
        """)

        # FTS5 virtual table for full-text search
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS docs_sections_fts USING fts5(
                slug,
                title,
                heading,
                content,
                content='docs_sections',
                content_rowid='id'
            )
        """)

        # Triggers to keep FTS in sync
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS docs_sections_ai AFTER INSERT ON docs_sections BEGIN
                INSERT INTO docs_sections_fts(rowid, slug, title, heading, content)
                VALUES (new.id, new.slug, new.title, new.heading, new.content);
            END
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS docs_sections_ad AFTER DELETE ON docs_sections BEGIN
                INSERT INTO docs_sections_fts(docs_sections_fts, rowid, slug, title, heading, content)
                VALUES ('delete', old.id, old.slug, old.title, old.heading, old.content);
            END
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS docs_sections_au AFTER UPDATE ON docs_sections BEGIN
                INSERT INTO docs_sections_fts(docs_sections_fts, rowid, slug, title, heading, content)
                VALUES ('delete', old.id, old.slug, old.title, old.heading, old.content);
                INSERT INTO docs_sections_fts(rowid, slug, title, heading, content)
                VALUES (new.id, new.slug, new.title, new.heading, new.content);
            END
        """)

        # Components table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS components (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                category TEXT,
                description TEXT NOT NULL,
                doc_slug TEXT,
                url TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS _meta (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # Indexes for faster queries
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_sections_slug ON docs_sections(slug)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_components_category ON components(category)"
        )

        conn.commit()


def clear_db() -> None:
    """Clear all data from the database (for re-indexing)."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM docs_sections")
        cursor.execute("DELETE FROM components")
        conn.commit()


def get_meta(key: str) -> str | None:
    """Get a value from the _meta table."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM _meta WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row["value"] if row else None


def set_meta(key: str, value: str) -> None:
    """Set a value in the _meta table."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO _meta (key, value) VALUES (?, ?)",
            (key, value),
        )
        conn.commit()


def insert_section(
    slug: str,
    title: str,
    heading: str,
    level: int,
    content: str,
    position: int,
    url: str,
) -> None:
    """Insert a documentation section."""
    insert_sections_many([(slug, title, heading, level, content, position, url)])


def insert_component(
    name: str,
    category: str | None,
    description: str,
    doc_slug: str | None,
    url: str | None,
) -> None:
    """Insert a component, updating if it already exists."""
    insert_components_many([(name, category, description, doc_slug, url)])


def insert_sections_many(
    rows: Iterable[tuple[str, str, str, int, str, int, str]],
    conn: sqlite3.Connection | None = None,
) -> int:
    """Bulk insert documentation sections."""
    rows = list(rows)
    if not rows:
        return 0
    owns_connection = conn is None
    context = get_connection() if owns_connection else nullcontext(conn)
    with context as conn:
        cursor = conn.cursor()
        cursor.executemany(
            """
            INSERT INTO docs_sections (slug, title, heading, level, content, position, url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        if owns_connection:
            conn.commit()
    return len(rows)


def insert_components_many(
    rows: Iterable[tuple[str, str | None, str, str | None, str | None]],
    conn: sqlite3.Connection | None = None,
) -> int:
    """Bulk insert components."""
    rows = list(rows)
    if not rows:
        return 0
    owns_connection = conn is None
    context = get_connection() if owns_connection else nullcontext(conn)
    with context as conn:
        cursor = conn.cursor()
        cursor.executemany(
            """
            INSERT OR REPLACE INTO components (name, category, description, doc_slug, url)
            VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )
        if owns_connection:
            conn.commit()
    return len(rows)


def search_sections(query: str, limit: int = 10, fuzzy: bool = True) -> list[DocResult]:
    """Search docs sections using FTS5.

    Args:
        query: Search query string.
        limit: Maximum results to return.
        fuzzy: If True, use phrase match + prefix expansion. If False, use exact quoting.
    """
    cache_key = f"{query}:{limit}:{fuzzy}"
    cached = _search_cache_get(cache_key)
    if cached is not None:
        return cached

    with get_connection() as conn:
        cursor = conn.cursor()

        if fuzzy:
            fts_query = build_fts_query(query)
        else:
            terms = query.strip().split()
            if not terms:
                return []
            fts_query = " ".join(f'"{term}"' for term in terms)

        cursor.execute(
            """
            SELECT
                s.slug,
                s.title,
                s.heading,
                s.content,
                s.url,
                highlight(docs_sections_fts, 3, '<b>', '</b>') as snippet,
                bm25(docs_sections_fts) as score
            FROM docs_sections_fts fts
            JOIN docs_sections s ON fts.rowid = s.id
            WHERE docs_sections_fts MATCH ?
            ORDER BY score
            LIMIT ?
            """,
            (fts_query, limit),
        )

        query_tokens = re.sub(r'[^\w\s]', '', query.lower()).split()
        results = []
        for row in cursor.fetchall():
            score = row["score"]
            # Boost results whose title contains a query token
            title_lower = row["title"].lower()
            if any(t in title_lower for t in query_tokens):
                score = score * 0.7
            snippet = row["snippet"]
            if not snippet or snippet == row["content"]:
                content = row["content"]
                snippet = content[:200] + "..." if len(content) > 200 else content
            results.append(
                DocResult(
                    slug=row["slug"],
                    title=row["title"],
                    score=abs(score),
                    snippet=snippet,
                    url=row["url"],
                )
            )

        # Re-sort after title boosting
        results.sort(key=lambda r: r.score)
        _search_cache_set(cache_key, results)
        return results


def get_page_sections(slug: str) -> DocPage | None:
    """Get all sections for a documentation page."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT slug, title, heading, level, content, url
            FROM docs_sections
            WHERE slug = ?
            ORDER BY position
            """,
            (slug,),
        )

        rows = cursor.fetchall()
        if not rows:
            return None

        sections = [
            DocSection(
                heading=row["heading"], level=row["level"], content=row["content"]
            )
            for row in rows
        ]

        return DocPage(
            slug=rows[0]["slug"],
            title=rows[0]["title"],
            url=rows[0]["url"],
            sections=sections,
        )


@functools.lru_cache(maxsize=512)
def get_page_sections_cached(slug: str) -> DocPage | None:
    """LRU-cached version of get_page_sections."""
    return get_page_sections(slug)


def list_all_components(category: str | None = None) -> list[ComponentInfo]:
    """List all components, optionally filtered by category."""
    with get_connection() as conn:
        cursor = conn.cursor()

        if category:
            cursor.execute(
                "SELECT * FROM components WHERE category = ? ORDER BY name", (category,)
            )
        else:
            cursor.execute("SELECT * FROM components ORDER BY name")

        return [
            ComponentInfo(
                name=row["name"],
                category=row["category"],
                description=row["description"],
                doc_slug=row["doc_slug"],
                url=row["url"],
            )
            for row in cursor.fetchall()
        ]


def search_components(query: str, limit: int = 20) -> list[ComponentInfo]:
    """Search components by name or description."""
    query = query.strip()
    if not query:
        return []
    like_query = f"%{query}%"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM components
            WHERE name LIKE ? OR description LIKE ?
            ORDER BY name
            LIMIT ?
            """,
            (like_query, like_query, limit),
        )
        return [
            ComponentInfo(
                name=row["name"],
                category=row["category"],
                description=row["description"],
                doc_slug=row["doc_slug"],
                url=row["url"],
            )
            for row in cursor.fetchall()
        ]


def get_component_by_name(name: str) -> ComponentInfo | None:
    """Get a component by its name."""
    # Normalize name - accept with or without rx. prefix
    search_name = name if name.startswith("rx.") else f"rx.{name}"

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM components WHERE name = ?", (search_name,))

        row = cursor.fetchone()
        if not row:
            # Try without prefix
            cursor.execute(
                "SELECT * FROM components WHERE name = ?", (name.replace("rx.", ""),)
            )
            row = cursor.fetchone()

        if not row:
            return None

        return ComponentInfo(
            name=row["name"],
            category=row["category"],
            description=row["description"],
            doc_slug=row["doc_slug"],
            url=row["url"],
        )


def get_stats() -> dict:
    """Get database statistics."""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) as count FROM docs_sections")
        sections_count = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(DISTINCT slug) as count FROM docs_sections")
        pages_count = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) as count FROM components")
        components_count = cursor.fetchone()["count"]

        return {
            "sections": sections_count,
            "pages": pages_count,
            "components": components_count,
        }


def is_index_ready() -> bool:
    """Return True if the database exists and has indexed content."""
    db_path = get_db_path()
    if not db_path.exists():
        return False
    try:
        stats = get_stats()
        return stats.get("sections", 0) > 0
    except Exception:
        return False


def build_fts_query(raw: str) -> str:
    """Build an FTS5 query with phrase match and prefix expansion."""
    tokens = re.sub(r'[^\w\s]', '', raw.lower()).split()
    if not tokens:
        return '""'
    phrase = " ".join(tokens)
    prefix_terms = " ".join(f'"{t}"*' for t in tokens if len(t) > 2)
    return f'"{phrase}" OR {prefix_terms}' if prefix_terms else f'"{phrase}"'


_search_cache: dict[str, tuple[float, list]] = {}
_SEARCH_CACHE_TTL = int(os.getenv("REFLEX_DOCS_CACHE_TTL", "300"))


def _search_cache_get(key: str) -> list | None:
    """Get a value from the search cache if it exists and is not expired."""
    if key in _search_cache:
        ts, value = _search_cache[key]
        if time.time() - ts < _SEARCH_CACHE_TTL:
            return value
        del _search_cache[key]
    return None


def _search_cache_set(key: str, value: list) -> None:
    """Set a value in the search cache."""
    _search_cache[key] = (time.time(), value)


def clear_search_cache() -> None:
    """Clear the entire search cache."""
    _search_cache.clear()


def list_pages(prefix: str | None = None, limit: int = 200) -> list[DocPageInfo]:
    """List available documentation pages, optionally filtered by slug prefix."""
    with get_connection() as conn:
        cursor = conn.cursor()
        if prefix:
            like_prefix = f"{prefix}%"
            cursor.execute(
                """
                SELECT slug, MAX(title) AS title, MAX(url) AS url
                FROM docs_sections
                WHERE slug LIKE ?
                GROUP BY slug
                ORDER BY slug
                LIMIT ?
                """,
                (like_prefix, limit),
            )
        else:
            cursor.execute(
                """
                SELECT slug, MAX(title) AS title, MAX(url) AS url
                FROM docs_sections
                GROUP BY slug
                ORDER BY slug
                LIMIT ?
                """,
                (limit,),
            )
        return [
            DocPageInfo(slug=row["slug"], title=row["title"], url=row["url"])
            for row in cursor.fetchall()
        ]
