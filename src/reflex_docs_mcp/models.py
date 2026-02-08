"""Pydantic data models for MCP tool inputs and outputs."""

from pydantic import BaseModel, Field


class DocSection(BaseModel):
    """A section within a documentation page."""

    heading: str = Field(description="Section heading text")
    level: int = Field(description="Heading level (1-3 for h1-h3)")
    content: str = Field(description="Markdown content of the section")


class DocResult(BaseModel):
    """A search result from the docs."""

    slug: str = Field(
        description="Document slug (e.g., 'components/rendering_iterables')"
    )
    title: str = Field(description="Document title")
    score: float = Field(description="Relevance score from search")
    snippet: str = Field(description="Excerpt from matching section")
    url: str = Field(description="Canonical docs URL")


class DocPage(BaseModel):
    """A full documentation page with sections."""

    slug: str = Field(description="Document slug")
    title: str = Field(description="Document title")
    url: str = Field(description="Canonical docs URL")
    sections: list[DocSection] = Field(description="Ordered list of sections")


class DocPageInfo(BaseModel):
    """Lightweight document page metadata."""

    slug: str = Field(description="Document slug")
    title: str = Field(description="Document title")
    url: str = Field(description="Canonical docs URL")


class ComponentInfo(BaseModel):
    """Information about a Reflex component."""

    name: str = Field(description="Component name (e.g., 'rx.box')")
    category: str | None = Field(
        default=None, description="Category (e.g., 'layout', 'forms')"
    )
    description: str = Field(description="Brief description of the component")
    doc_slug: str | None = Field(
        default=None, description="Slug of the documentation page"
    )
    url: str | None = Field(
        default=None, description="URL to the component documentation"
    )
