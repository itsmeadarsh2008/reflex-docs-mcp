"""Markdown parser for Reflex documentation files."""

import re
import yaml
from pathlib import Path
from dataclasses import dataclass

# Base URL for Reflex docs
REFLEX_DOCS_BASE_URL = "https://reflex.dev/docs"


@dataclass
class ParsedSection:
    """A parsed section from a markdown file."""

    heading: str
    level: int
    content: str
    position: int


@dataclass
class ParsedDoc:
    """A fully parsed documentation file."""

    slug: str
    title: str
    url: str
    sections: list[ParsedSection]
    components: list[str]  # Component names from frontmatter


def extract_frontmatter(content: str) -> tuple[dict, str]:
    """Extract YAML frontmatter from markdown content.

    Returns:
        Tuple of (frontmatter dict, remaining content)
    """
    if not content.startswith("---"):
        return {}, content

    # Find the closing ---
    end_match = re.search(r"\n---\s*\n", content[3:])
    if not end_match:
        return {}, content

    # Extract frontmatter YAML
    frontmatter_end = end_match.end() + 3
    frontmatter_yaml = content[3 : end_match.start() + 3]
    remaining_content = content[frontmatter_end:]

    try:
        frontmatter = yaml.safe_load(frontmatter_yaml) or {}
    except yaml.YAMLError:
        frontmatter = {}

    return frontmatter, remaining_content


def split_into_sections(content: str) -> list[ParsedSection]:
    """Split markdown content into sections by headings.

    Handles:
    - # H1, ## H2, ### H3 headings
    - Preserves code blocks (doesn't split on # inside code)
    - Preserves markdown formatting
    """
    sections = []

    # Regular expression to match headings (not inside code blocks)
    # We need to be careful not to match # inside fenced code blocks

    # First, temporarily replace code blocks with placeholders
    code_blocks = []

    def save_code_block(match):
        code_blocks.append(match.group(0))
        return f"<<<CODE_BLOCK_{len(code_blocks) - 1}>>>"

    # Match fenced code blocks (``` or ~~~)
    content_protected = re.sub(
        r"```.*?```|~~~.*?~~~", save_code_block, content, flags=re.DOTALL
    )

    # Now split by headings
    heading_pattern = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)

    # Find all headings
    matches = list(heading_pattern.finditer(content_protected))

    if not matches:
        # No headings, return entire content as one section
        # Restore code blocks
        for i, block in enumerate(code_blocks):
            content = content.replace(f"<<<CODE_BLOCK_{i}>>>", block)
        return [ParsedSection(heading="", level=0, content=content.strip(), position=0)]

    # Process each section
    for i, match in enumerate(matches):
        level = len(match.group(1))
        heading = match.group(2).strip()

        # Get content between this heading and the next (or end of file)
        start = match.end()
        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(content_protected)

        section_content = content_protected[start:end].strip()

        # Restore code blocks in this section
        for j, block in enumerate(code_blocks):
            section_content = section_content.replace(f"<<<CODE_BLOCK_{j}>>>", block)

        sections.append(
            ParsedSection(
                heading=heading, level=level, content=section_content, position=i
            )
        )

    # Handle any content before the first heading
    content_before = content_protected[: matches[0].start()].strip()
    if content_before:
        for j, block in enumerate(code_blocks):
            content_before = content_before.replace(f"<<<CODE_BLOCK_{j}>>>", block)
        sections.insert(
            0, ParsedSection(heading="", level=0, content=content_before, position=-1)
        )
        # Re-number positions
        for i, section in enumerate(sections):
            section.position = i

    return sections


def extract_first_sentence(content: str) -> str:
    """Extract the first sentence from content for a description."""
    # Remove code blocks
    content = re.sub(r"```.*?```", "", content, flags=re.DOTALL)
    # Remove inline code
    content = re.sub(r"`[^`]+`", "", content)
    # Remove markdown links but keep text
    content = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", content)
    # Remove images
    content = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", content)
    # Remove special blocks (md alert, md definition, etc.)
    content = re.sub(r"```md\s+\w+.*?```", "", content, flags=re.DOTALL)

    # Find first sentence
    content = content.strip()
    sentences = re.split(r"(?<=[.!?])\s+", content)
    if sentences:
        first = sentences[0].strip()
        # Clean up any remaining markdown
        first = re.sub(r"[#*_]", "", first)
        return first[:200] if len(first) > 200 else first

    return content[:200] if content else "No description available."


def file_path_to_slug(file_path: Path, docs_root: Path) -> str:
    """Convert a file path to a documentation slug.

    Example: docs/library/layout/box.md -> library/layout/box
    """
    relative = file_path.relative_to(docs_root)
    # Remove .md or .mdx extension
    slug = str(relative.with_suffix("")).replace("\\", "/")
    return slug


def parse_doc_file(file_path: Path, docs_root: Path) -> ParsedDoc:
    """Parse a markdown documentation file.

    Args:
        file_path: Path to the markdown file
        docs_root: Root directory of the docs (e.g., docs_src/docs)

    Returns:
        ParsedDoc with all extracted information
    """
    content = file_path.read_text(encoding="utf-8")

    # Extract frontmatter
    frontmatter, body = extract_frontmatter(content)

    # Get slug and URL
    slug = file_path_to_slug(file_path, docs_root)
    url = f"{REFLEX_DOCS_BASE_URL}/{slug}"

    # Extract components from frontmatter
    components = frontmatter.get("components", [])
    if isinstance(components, str):
        components = [components]

    # Split into sections
    sections = split_into_sections(body)

    # Determine title from first H1 or filename
    title = None
    for section in sections:
        if section.level == 1 and section.heading:
            title = section.heading
            break

    if not title:
        # Use filename as title
        title = file_path.stem.replace("_", " ").replace("-", " ").title()

    return ParsedDoc(
        slug=slug, title=title, url=url, sections=sections, components=components
    )


def extract_component_description(parsed_doc: ParsedDoc) -> str:
    """Extract a component description from a parsed doc."""
    for section in parsed_doc.sections:
        if section.content:
            return extract_first_sentence(section.content)
    return "No description available."


def get_category_from_slug(slug: str) -> str | None:
    """Extract category from a library component slug.

    Example: library/layout/box -> layout
    """
    parts = slug.split("/")
    if len(parts) >= 2 and parts[0] == "library":
        return parts[1]
    return None
