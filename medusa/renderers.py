"""Content renderers for Medusa.

This module contains implementations of the ContentRenderer protocol
for different content types. Each renderer handles a single responsibility
(SRP) - rendering one type of content.

Key classes:
- MarkdownRenderer: Renders Markdown to HTML with syntax highlighting.
- HTMLRenderer: Passes through HTML content.
- JinjaRenderer: Handles Jinja template content.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

import mistune

from .utils import strip_hashtags

if TYPE_CHECKING:
    pass


def _generate_heading_id(text: str) -> str:
    """Generate a URL-friendly ID from heading text.

    Args:
        text: The heading text.

    Returns:
        URL-friendly slug suitable for anchor links.
    """
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug.strip("-")


def _rewrite_image_path(src: str, folder: str) -> str:
    """Rewrite image source paths to point to assets directory.

    Args:
        src: Original image source.
        folder: Folder containing the page.

    Returns:
        Rewritten image source path.
    """
    if src.startswith(("http://", "https://", "//", "/")) or "{{" in src:
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
        self.headings: list = []
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
        # Import here to avoid circular imports
        from .content import Heading as HeadingClass

        base_id = _generate_heading_id(text)

        if base_id in self._heading_id_counts:
            self._heading_id_counts[base_id] += 1
            heading_id = f"{base_id}-{self._heading_id_counts[base_id]}"
        else:
            self._heading_id_counts[base_id] = 0
            heading_id = base_id

        self.headings.append(HeadingClass(id=heading_id, text=text, level=level))

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
        escaped = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        lang_class = f' class="language-{info}"' if info else ""
        return f"<pre><code{lang_class}>{escaped}</code></pre>\n"


class MarkdownRenderer:
    """Renders Markdown content to HTML.

    This renderer handles Markdown files, converting them to HTML
    with syntax highlighting and heading extraction for TOC.
    """

    @property
    def source_type(self) -> str:
        """Return the source type identifier."""
        return "markdown"

    def can_render(self, path: Path) -> bool:
        """Check if this renderer can handle the given file.

        Args:
            path: Path to the source file.

        Returns:
            True if the file is a Markdown file.
        """
        return path.suffix.lower() == ".md"

    def render(self, content: str, folder: str) -> tuple[str, list]:
        """Render Markdown content to HTML.

        Args:
            content: Markdown source content.
            folder: Folder containing the page.

        Returns:
            Tuple of (rendered HTML, list of Heading objects).
        """
        cleaned = strip_hashtags(content)
        renderer = _HighlightRenderer(folder)
        markdown = mistune.create_markdown(
            renderer=renderer, plugins=["strikethrough", "footnotes", "table", "url"]
        )
        html = markdown(cleaned)
        return html, renderer.headings


class HTMLRenderer:
    """Passes through HTML content unchanged.

    This renderer handles plain HTML files that don't need
    Markdown processing or Jinja templating.
    """

    @property
    def source_type(self) -> str:
        """Return the source type identifier."""
        return "html"

    def can_render(self, path: Path) -> bool:
        """Check if this renderer can handle the given file.

        Args:
            path: Path to the source file.

        Returns:
            True if the file is a plain HTML file.
        """
        from .utils import is_html

        return is_html(path)

    def render(self, content: str, folder: str) -> tuple[str, list]:
        """Pass through HTML content.

        Args:
            content: HTML source content.
            folder: Folder containing the page (unused).

        Returns:
            Tuple of (content unchanged, empty heading list).
        """
        return content, []


class JinjaContentRenderer:
    """Handles Jinja template content.

    This renderer identifies Jinja template files. The actual
    Jinja rendering is deferred to the TemplateEngine.
    """

    @property
    def source_type(self) -> str:
        """Return the source type identifier."""
        return "jinja"

    def can_render(self, path: Path) -> bool:
        """Check if this renderer can handle the given file.

        Args:
            path: Path to the source file.

        Returns:
            True if the file is a Jinja template.
        """
        from .utils import is_template

        return is_template(path)

    def render(self, content: str, folder: str) -> tuple[str, list]:
        """Return Jinja content for later processing.

        Args:
            content: Jinja template source content.
            folder: Folder containing the page (unused).

        Returns:
            Tuple of (content unchanged, empty heading list).
            Note: Actual Jinja rendering happens in TemplateEngine.
        """
        return content, []


class RendererRegistry:
    """Registry for content renderers.

    This registry allows adding new renderers without modifying
    existing code, following the Open/Closed Principle.
    """

    def __init__(self):
        """Initialize the registry with default renderers."""
        self._renderers: list = []
        # Register default renderers in priority order
        self.register(MarkdownRenderer())
        self.register(JinjaContentRenderer())
        self.register(HTMLRenderer())

    def register(self, renderer) -> None:
        """Register a new renderer.

        Args:
            renderer: A ContentRenderer implementation.
        """
        self._renderers.append(renderer)

    def get_renderer(self, path: Path):
        """Get the appropriate renderer for a file.

        Args:
            path: Path to the source file.

        Returns:
            The first renderer that can handle the file, or None.
        """
        for renderer in self._renderers:
            if renderer.can_render(path):
                return renderer
        return None


# Default renderer registry instance
default_renderer_registry = RendererRegistry()
