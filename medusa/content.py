"""Content processing for Medusa.

This module handles loading and processing of content files (Markdown and Jinja templates).
It extracts metadata, renders content, and creates Page objects representing site pages.

Key classes:
- Page: Dataclass representing a site page with all its metadata.
- ContentProcessor: Class for processing content files and building Page instances.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import mistune
import yaml

from .utils import (
    extract_date_from_name,
    extract_tags,
    first_paragraph,
    is_html,
    is_markdown,
    is_template,
    slugify,
    strip_hashtags,
    titleize,
)

IMAGE_SRC_RE = re.compile(r'<img\s+[^>]*src="([^"]+)"', re.IGNORECASE)
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _extract_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Extract YAML frontmatter from content.

    Args:
        text: Raw file content.

    Returns:
        Tuple of (frontmatter dict, remaining content).
    """
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    try:
        data = yaml.safe_load(match.group(1)) or {}
        if not isinstance(data, dict):
            return {}, text
        return data, text[match.end() :]
    except yaml.YAMLError:
        return {}, text


@dataclass
class Heading:
    """Represents a heading extracted from markdown content for TOC generation.

    Attributes:
        id: Anchor ID for the heading (URL-friendly slug).
        text: The text content of the heading.
        level: Heading level (1-6).
    """

    id: str
    text: str
    level: int


def _generate_heading_id(text: str) -> str:
    """Generate a URL-friendly ID from heading text.

    Args:
        text: The heading text.

    Returns:
        URL-friendly slug suitable for anchor links.
    """
    # Convert to lowercase, replace spaces with hyphens, remove special chars
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug.strip("-")


def _extract_excerpt(text: str) -> str:
    """Extract the first paragraph from markdown text.

    Skips the title heading (# Title) and returns the first actual paragraph.

    Args:
        text: Markdown text content.

    Returns:
        The first paragraph as plain text, or empty string if none found.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    for para in paragraphs:
        # Skip headings
        if para.startswith("#"):
            continue
        # Skip images, code blocks, and other non-text elements
        if para.startswith(("![", "```", "---")):
            continue
        # Clean up the paragraph: collapse whitespace
        cleaned = " ".join(para.split())
        return cleaned
    return ""


@dataclass
class Page:
    """Represents a site page with all its metadata and content.

    Attributes:
        title: Human-readable title of the page.
        body: Raw body text from the source file.
        content: Rendered HTML content.
        description: Short description, often from first paragraph.
        excerpt: Full first paragraph (markdown files only).
        url: URL path for the page.
        slug: URL-friendly slug.
        date: Publication date.
        tags: List of tags extracted from content.
        draft: Whether this is a draft page.
        layout: Layout template to use.
        group: Content group (e.g., 'posts').
        path: Path to the source file.
        folder: Folder path relative to site directory.
        filename: Name of the source file.
        source_type: "markdown", "html", or "jinja".
    """

    title: str
    body: str
    content: str
    description: str
    excerpt: str
    url: str
    slug: str
    date: datetime
    tags: list[str]
    draft: bool
    layout: str
    group: str
    path: Path
    folder: str
    filename: str
    source_type: str  # "markdown" | "html" | "jinja"
    frontmatter: dict[str, Any] = field(default_factory=dict)
    toc: list[Heading] = field(default_factory=list)


def _rewrite_image_path(src: str, folder: str) -> str:
    """Rewrite image source paths to point to assets directory.

    Args:
        src: Original image source.
        folder: Folder containing the page.

    Returns:
        Rewritten image source path.
    """
    if src.startswith(("http://", "https://", "//", "/")):
        return src
    prefix = Path(folder) if folder else Path()
    normalized = (prefix / src).as_posix()
    return f"/assets/images/{normalized}"


class _HighlightRenderer(mistune.HTMLRenderer):
    """Custom Markdown renderer with image path rewriting and syntax highlighting.

    Attributes:
        folder: Folder containing the page being rendered.
        headings: List of Heading objects extracted during rendering.
    """

    def __init__(self, folder: str):
        """Initialize the renderer.

        Args:
            folder: Folder path for image rewriting.
        """
        super().__init__(escape=False)
        self.folder = folder
        self.headings: list[Heading] = []
        self._heading_id_counts: dict[str, int] = {}

    def heading(self, text: str, level: int, **attrs) -> str:
        """Render a heading with auto-generated ID and track for TOC.

        Args:
            text: Heading text content.
            level: Heading level (1-6).
            **attrs: Additional attributes.

        Returns:
            HTML heading tag with id attribute.
        """
        base_id = _generate_heading_id(text)

        # Handle duplicate IDs by appending a counter
        if base_id in self._heading_id_counts:
            self._heading_id_counts[base_id] += 1
            heading_id = f"{base_id}-{self._heading_id_counts[base_id]}"
        else:
            self._heading_id_counts[base_id] = 0
            heading_id = base_id

        # Track this heading for TOC
        self.headings.append(Heading(id=heading_id, text=text, level=level))

        return f'<h{level} id="{heading_id}">{text}</h{level}>\n'

    def image(self, text: str, url: str | None = None, title: str | None = None):
        """Render an image tag with rewritten source.

        Args:
            text: Alt text value from markdown.
            url: Image source URL.
            title: Title attribute.

        Returns:
            HTML image tag string.
        """
        src = _rewrite_image_path(url or "", self.folder)
        return super().image(text, src, title)

    def block_code(self, code: str, info: str | None = None) -> str:
        """Render a code block with Pygments syntax highlighting.

        Args:
            code: The code content.
            info: Language identifier (e.g., 'python', 'javascript').

        Returns:
            HTML string with highlighted code.
        """
        if info:
            try:
                from pygments import highlight
                from pygments.formatters import HtmlFormatter
                from pygments.lexers import get_lexer_by_name

                lexer = get_lexer_by_name(info, stripall=True)
                formatter = HtmlFormatter(nowrap=False, cssclass="highlight")
                return highlight(code, lexer, formatter)
            except Exception:
                pass
        # Fallback: plain code block
        escaped = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        lang_class = f' class="language-{info}"' if info else ""
        return f"<pre><code{lang_class}>{escaped}</code></pre>\n"


class ContentProcessor:
    """Processes content files and builds Page objects.

    Attributes:
        site_dir: Directory containing site content.
    """

    def __init__(self, site_dir: Path):
        """Initialize the content processor.

        Args:
            site_dir: Path to the site content directory.
        """
        self.site_dir = site_dir

    def load(self, include_drafts: bool = False) -> list[Page]:
        """Load all content files and create Page objects.

        Args:
            include_drafts: Whether to include draft pages.

        Returns:
            List of Page objects.
        """
        pages: list[Page] = []
        for path in self._iter_source_files(include_drafts):
            draft = path.name.startswith("_")
            page = self._build_page(path, draft=draft)
            pages.append(page)
        return pages

    def _iter_source_files(self, include_drafts: bool) -> Iterable[Path]:
        """Iterate over all source files in the site directory.

        Yields:
            Paths to content files (markdown, html, and jinja templates).
        """
        for path in self.site_dir.rglob("*"):
            if path.is_dir():
                continue
            rel = path.relative_to(self.site_dir)
            parts = rel.parts
            if any(part.startswith("_") for part in parts[:-1]):
                continue
            if rel.name.startswith("_") and not include_drafts:
                continue
            if is_markdown(path) or is_template(path) or is_html(path):
                yield path

    def _build_page(self, path: Path, draft: bool) -> Page:
        """Build a Page object from a source file.

        Args:
            path: Path to the source file.
            draft: Whether this is a draft.

        Returns:
            Page object.
        """
        rel = path.relative_to(self.site_dir)
        folder = str(rel.parent.as_posix()) if rel.parent != Path(".") else ""
        filename = path.name
        raw_body = path.read_text(encoding="utf-8")

        frontmatter, body = _extract_frontmatter(raw_body)

        date = extract_date_from_name(path.stem) or datetime.fromtimestamp(
            path.stat().st_mtime
        )
        layout = self._resolve_layout(path, folder)

        slug = slugify(path.stem)
        url = self._derive_url(rel, slug)

        toc: list[Heading] = []
        excerpt: str = ""

        if is_markdown(path):
            tags = extract_tags(body)
            render_source = strip_hashtags(body)
            content, toc = self._render_markdown(render_source, folder)
            title = self._resolve_title(body, filename)
            description = first_paragraph(strip_hashtags(body))
            excerpt = _extract_excerpt(strip_hashtags(body))
            source_type = "markdown"
        elif is_html(path):
            tags = extract_tags(body)
            render_source = strip_hashtags(body)
            content = render_source
            title = self._resolve_title(body, filename)
            description = first_paragraph(strip_hashtags(body))
            source_type = "html"
        else:
            # Jinja templates
            tags = extract_tags(body)
            render_source = strip_hashtags(body)
            content = render_source
            title = self._resolve_title(body, filename)
            description = first_paragraph(strip_hashtags(body))
            source_type = "jinja"

        return Page(
            title=title,
            body=body,
            content=self._rewrite_inline_images(content, folder),
            description=description,
            excerpt=excerpt,
            url=url,
            slug=slug,
            date=date,
            tags=tags,
            draft=draft,
            layout=layout,
            group=self._group_from_folder(folder),
            path=path,
            folder=folder,
            filename=filename,
            source_type=source_type,
            frontmatter=frontmatter,
            toc=toc,
        )

    def _render_markdown(self, text: str, folder: str) -> tuple[str, list[Heading]]:
        """Render markdown text to HTML and extract headings.

        Args:
            text: Markdown text to render.
            folder: Folder containing the page (for image path rewriting).

        Returns:
            Tuple of (rendered HTML, list of Heading objects for TOC).
        """
        cleaned = strip_hashtags(text)
        renderer = _HighlightRenderer(folder)
        markdown = mistune.create_markdown(
            renderer=renderer, plugins=["strikethrough", "footnotes", "table", "url"]
        )
        content = markdown(cleaned)
        return content, renderer.headings

    def _rewrite_inline_images(self, html: str, folder: str) -> str:
        def repl(match: re.Match) -> str:
            src = match.group(1)
            rewritten = _rewrite_image_path(src, folder)
            return match.group(0).replace(src, rewritten)

        return IMAGE_SRC_RE.sub(repl, html)

    def _resolve_title(self, body: str, filename: str) -> str:
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped.lstrip("# ").strip()
        return titleize(filename)

    def _resolve_layout(self, path: Path, folder: str) -> str:
        name = path.stem
        layout_dir = self.site_dir / "_layouts"
        group = self._group_from_folder(folder)
        candidates: list[str] = []
        if folder:
            # Most specific: folder-based layout matching the full folder/name path.
            candidates.append(f"{folder}/{name}")
            # Next: layout matching just the top-level folder.
            candidates.append(group)
        else:
            # Root-level file: try a layout that matches the filename.
            candidates.append(name)
        # Fallback: default layout.
        candidates.append("default")
        for candidate in candidates:
            for suffix in (".html.jinja", ".jinja", ".html", ""):
                target = layout_dir / f"{candidate}{suffix}"
                if target.exists():
                    return candidate
        return "default"

    def _group_from_folder(self, folder: str) -> str:
        if not folder:
            return ""
        first = Path(folder).parts[0]
        return first

    def _derive_url(self, rel: Path, slug: str) -> str:
        parent = "" if rel.parent == Path(".") else rel.parent.as_posix()
        if rel.stem == "index" and not parent:
            return "/"
        segments = [p for p in rel.parent.parts if p]
        if slug == "index":
            url_parts = segments
        else:
            url_parts = segments + [slug]
        path = "/".join(url_parts)
        return f"/{path}/" if path else "/"
