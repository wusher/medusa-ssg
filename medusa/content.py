"""Content processing for Medusa.

This module handles loading and processing of content files (Markdown and Jinja templates).
It extracts metadata, renders content, and creates Page objects representing site pages.

Key classes:
- Page: Dataclass representing a site page with all its metadata.
- ContentProcessor: Class for processing content files and building Page instances.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, List
import os
import re

import mistune
import yaml

from .utils import (
    extract_date_from_name,
    extract_tags,
    first_paragraph,
    get_code_language,
    is_code_file,
    is_internal_path,
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
class Page:
    """Represents a site page with all its metadata and content.

    Attributes:
        title: Human-readable title of the page.
        body: Raw body text from the source file.
        content: Rendered HTML content.
        description: Short description, often from first paragraph.
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
        source_type: "markdown" or "jinja".
    """

    title: str
    body: str
    content: str
    description: str
    url: str
    slug: str
    date: datetime
    tags: List[str]
    draft: bool
    layout: str
    group: str
    path: Path
    folder: str
    filename: str
    source_type: str  # "markdown" | "jinja" | "code"
    frontmatter: dict[str, Any] = field(default_factory=dict)


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
    """

    def __init__(self, folder: str):
        """Initialize the renderer.

        Args:
            folder: Folder path for image rewriting.
        """
        super().__init__(escape=False)
        self.folder = folder

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
                from pygments.lexers import get_lexer_by_name
                from pygments.formatters import HtmlFormatter

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

    def load(self, include_drafts: bool = False) -> List[Page]:
        """Load all content files and create Page objects.

        Args:
            include_drafts: Whether to include draft pages.

        Returns:
            List of Page objects.
        """
        pages: List[Page] = []
        for path in self._iter_source_files(include_drafts):
            draft = path.name.startswith("_")
            page = self._build_page(path, draft=draft)
            pages.append(page)
        return pages

    def _iter_source_files(self, include_drafts: bool) -> Iterable[Path]:
        """Iterate over all source files in the site directory.

        Yields:
            Paths to content files (markdown, templates, and code files in subfolders).
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
            if is_markdown(path) or is_template(path):
                yield path
            # Code files only in subfolders (not root site/)
            elif is_code_file(path) and len(parts) > 1:
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

        # Extract frontmatter for markdown and jinja files
        if is_code_file(path):
            frontmatter: dict[str, Any] = {}
            body = raw_body
        else:
            frontmatter, body = _extract_frontmatter(raw_body)

        date = extract_date_from_name(path.stem) or datetime.fromtimestamp(
            path.stat().st_mtime
        )
        layout = self._resolve_layout(path, folder)

        slug = slugify(path.stem)
        url = self._derive_url(rel, slug)

        if is_code_file(path):
            # Code files: wrap in code block and render
            lang = get_code_language(path)
            markdown_source = f"```{lang}\n{body}\n```"
            content = self._render_markdown(markdown_source, folder)
            title = titleize(filename)
            tags: List[str] = []
            description = self._extract_code_description(body)
            source_type = "code"
        elif is_markdown(path):
            tags = extract_tags(body)
            render_source = strip_hashtags(body)
            content = self._render_markdown(render_source, folder)
            title = self._resolve_title(body, filename)
            description = first_paragraph(strip_hashtags(body))
            source_type = "markdown"
        else:
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
        )

    def _render_markdown(self, text: str, folder: str) -> str:
        cleaned = strip_hashtags(text)
        renderer = _HighlightRenderer(folder)
        markdown = mistune.create_markdown(
            renderer=renderer, plugins=["strikethrough", "footnotes", "table", "url"]
        )
        return markdown(cleaned)

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

    def _extract_code_description(self, code: str) -> str:
        """Extract description from code file (first comment or empty).

        Args:
            code: Source code content.

        Returns:
            Description string, limited to 160 characters.
        """
        lines = code.strip().splitlines()
        if not lines:
            return ""

        first_line = lines[0].strip()

        # Python/Ruby/Shell: # comment (but not shebang)
        if first_line.startswith("#") and not first_line.startswith("#!"):
            return first_line.lstrip("#").strip()[:160]
        # C-style: // comment
        if first_line.startswith("//"):
            return first_line.lstrip("/").strip()[:160]
        # Docstring: """ or '''
        if first_line.startswith(('"""', "'''")):
            delimiter = first_line[:3]
            # Single line docstring
            if first_line.endswith(delimiter) and len(first_line) > 6:
                return first_line[3:-3].strip()[:160]
            # Multi-line: get first content line
            for line in lines[1:]:
                stripped = line.strip()
                if stripped and not stripped.startswith(delimiter):
                    return stripped[:160]
                if delimiter in stripped:
                    break
        return ""

    def _resolve_layout(self, path: Path, folder: str) -> str:
        name = path.stem
        layout_dir = self.site_dir / "_layouts"
        if "[" in name and "]" in name:
            return name.split("[", 1)[1].split("]", 1)[0]
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
