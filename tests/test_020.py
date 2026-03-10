"""Tests for reflex-docs-mcp 0.2.0 new and enhanced tools."""

import pytest

from reflex_docs_mcp import database
from reflex_docs_mcp import server as _srv

# @mcp.tool wraps functions in FunctionTool; unwrap via .fn to call directly.
search_docs = _srv.search_docs.fn
get_doc = _srv.get_doc.fn
get_code_examples = _srv.get_code_examples.fn
decode_error = _srv.decode_error.fn
get_changelog = _srv.get_changelog.fn
get_migration_guide = _srv.get_migration_guide.fn
search_api_reference = _srv.search_api_reference.fn
get_component_props = _srv.get_component_props.fn
list_recipes = _srv.list_recipes.fn


@pytest.fixture(autouse=True, scope="module")
def _init_db():
    """Ensure database tables exist."""
    database.init_db()


# --- search_docs (enhanced) ---

class TestSearchDocs:
    def test_valid_query(self):
        result = search_docs("state")
        assert isinstance(result, list)

    def test_empty_query(self):
        result = search_docs("")
        assert isinstance(result, list)

    def test_fuzzy_flag(self):
        result = search_docs("button", fuzzy=False)
        assert isinstance(result, list)

    def test_include_content(self):
        result = search_docs("state", include_content=True, limit=2)
        assert isinstance(result, list)


# --- get_doc (enhanced) ---

class TestGetDoc:
    def test_valid_slug(self):
        # May return None if slug doesn't exist in test DB
        result = get_doc("nonexistent-slug-xyz")
        assert result is None or isinstance(result, dict)

    def test_extract_code(self):
        result = get_doc("nonexistent-slug-xyz", extract_code=True)
        assert result is None or ("code_blocks" in result)

    def test_empty_slug(self):
        result = get_doc("")
        assert result is None or isinstance(result, dict)


# --- get_code_examples ---

class TestGetCodeExamples:
    def test_valid_topic(self):
        result = get_code_examples("state")
        assert "topic" in result
        assert "count" in result
        assert "examples" in result
        assert isinstance(result["examples"], list)

    def test_empty_topic(self):
        result = get_code_examples("")
        assert "topic" in result
        assert "count" in result
        assert isinstance(result["examples"], list)


# --- decode_error ---

class TestDecodeError:
    def test_valid_error(self):
        result = decode_error("TypeError: cannot serialize state var")
        assert "error_class" in result
        assert "rx_symbols" in result
        assert "relevant_docs" in result
        assert "search_queries_used" in result
        assert result["error_class"] == "TypeError"

    def test_empty_error(self):
        result = decode_error("")
        assert "error_class" in result
        assert "relevant_docs" in result

    def test_rx_symbol_extraction(self):
        result = decode_error("rx.State raised rx.EventError")
        assert "rx.State" in result["rx_symbols"]
        assert "rx.EventError" in result["rx_symbols"] or "EventError" == result["error_class"]


# --- get_changelog ---

class TestGetChangelog:
    def test_no_version(self, monkeypatch):
        monkeypatch.setattr(
            "reflex_docs_mcp.server.fetch",
            lambda url, ttl=3600: "## 0.6.1 (2025-01-10)\n\nSome changes\n\n## 0.6.0 (2025-01-01)\n\nOther changes\n",
        )
        result = get_changelog()
        assert "requested_version" in result
        assert "returned_count" in result
        assert "source" in result
        assert "releases" in result

    def test_specific_version(self, monkeypatch):
        monkeypatch.setattr(
            "reflex_docs_mcp.server.fetch",
            lambda url, ttl=3600: "## 0.6.1 (2025-01-10)\n\nFixes\n\n## 0.6.0 (2025-01-01)\n\nRelease\n",
        )
        result = get_changelog(version="0.6.1")
        assert "releases" in result

    def test_fetch_failure(self, monkeypatch):
        monkeypatch.setattr("reflex_docs_mcp.server.fetch", lambda url, ttl=3600: None)
        result = get_changelog()
        assert result["returned_count"] == 0
        assert "error" in result


# --- get_migration_guide ---

class TestGetMigrationGuide:
    def test_valid_versions(self, monkeypatch):
        monkeypatch.setattr(
            "reflex_docs_mcp.server.fetch",
            lambda url, ttl=3600: "## 0.6.0 (2025-01-01)\n\n**Breaking** removed old API\n\nOther changes\n",
        )
        result = get_migration_guide("0.5.0", "0.6.0")
        assert "from_version" in result
        assert "to_version" in result
        assert "breaking_changes" in result
        assert "relevant_docs" in result
        assert "changelog_section" in result

    def test_nonexistent_version(self, monkeypatch):
        monkeypatch.setattr("reflex_docs_mcp.server.fetch", lambda url, ttl=3600: None)
        result = get_migration_guide("0.0.0", "0.0.1")
        assert "from_version" in result
        assert "to_version" in result


# --- search_api_reference ---

class TestSearchApiReference:
    def test_valid_symbol(self, monkeypatch):
        monkeypatch.setattr("reflex_docs_mcp.server.fetch", lambda url, ttl=3600: None)
        result = search_api_reference("rx.State")
        assert "symbol" in result
        assert "source" in result
        assert "headings" in result
        assert "code_blocks" in result
        assert "tables" in result

    def test_empty_symbol(self, monkeypatch):
        monkeypatch.setattr("reflex_docs_mcp.server.fetch", lambda url, ttl=3600: None)
        result = search_api_reference("")
        assert "symbol" in result
        assert isinstance(result["headings"], list)


# --- get_component_props ---

class TestGetComponentProps:
    def test_nonexistent_component(self):
        result = get_component_props("rx.nonexistent_widget_xyz")
        assert "component" in result
        assert "total_props" in result
        assert "props" in result
        assert "error" in result

    def test_empty_name(self):
        result = get_component_props("")
        assert "component" in result
        assert "props" in result


# --- list_recipes ---

class TestListRecipes:
    def test_no_category(self):
        result = list_recipes()
        assert "category_filter" in result
        assert "count" in result
        assert "recipes" in result
        assert isinstance(result["recipes"], list)

    def test_with_category(self):
        result = list_recipes(category="auth")
        assert "category_filter" in result
        assert result["category_filter"] == "auth"
        assert isinstance(result["recipes"], list)
