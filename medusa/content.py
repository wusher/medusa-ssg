"""Content processing for Medusa.

This module handles loading and processing of content files (Markdown and Jinja templates).
It extracts metadata, renders content, and creates Page objects representing site pages.

Key classes:
- Page: Dataclass representing a site page with all its metadata.
- ContentProcessor: Class for processing content files and building Page instances.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List
import os
import re

import mistune

from .utils import (
    extract_date_from_name,
    extract_tags,
    first_paragraph,
    is_internal_path,
    is_markdown,
    is_template,
    slugify,
    strip_hashtags,
    titleize,
)


IMAGE_SRC_RE = re.compile(r'<img\s+[^>]*src="([^"]+)"', re.IGNORECASE)


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
    source_type: str  # "markdown" | "jinja"


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


class _ImageRenderer(mistune.HTMLRenderer):
    """Custom Markdown renderer that rewrites image paths.

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
            Paths to content files.
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
        body = path.read_text(encoding="utf-8")
        tags = extract_tags(body)
        date = extract_date_from_name(path.stem) or datetime.fromtimestamp(
            path.stat().st_mtime
        )
        layout = self._resolve_layout(path, folder)
        slug = slugify(path.stem)
        url = self._derive_url(rel, slug)
        title = self._resolve_title(body, filename)

        render_source = strip_hashtags(body)
        if is_markdown(path):
            content = self._render_markdown(render_source, folder)
            source_type = "markdown"
        else:
            content = render_source
            source_type = "jinja"

        description = first_paragraph(strip_hashtags(body))

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
        )

    def _render_markdown(self, text: str, folder: str) -> str:
        cleaned = strip_hashtags(text)
        renderer = _ImageRenderer(folder)
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
