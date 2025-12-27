"""Content processing for Medusa.

This module handles loading and processing of content files (Markdown and Jinja templates).
It extracts metadata, renders content, and creates Page objects representing site pages.

Key classes:
- Page: Dataclass representing a site page with all its metadata.
- Heading: Dataclass representing a heading for TOC generation.
- ContentProcessor: Facade for processing content files and building Page instances.
- FileContentLoader: Implementation of ContentLoader protocol for file-based content.
- DefaultPageBuilder: Implementation of PageBuilder protocol.

Design principles:
- Single Responsibility: Each class has one reason to change.
- Open/Closed: New renderers/extractors can be added without modifying existing code.
- Dependency Inversion: High-level modules depend on abstractions (protocols).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .extractors import (
    CompositeMetadataExtractor,
    DescriptionExtractor,
    default_metadata_extractor,
    extract_frontmatter,
)
from .renderers import (
    RendererRegistry,
    _generate_heading_id,  # noqa: F401 - re-exported for backward compatibility
    _HighlightRenderer,  # noqa: F401 - re-exported for backward compatibility
    _rewrite_image_path,
    default_renderer_registry,
)
from .utils import (
    is_html,
    is_markdown,
    is_template,
    slugify,
    strip_hashtags,
    titleize,
)

if TYPE_CHECKING:
    pass

IMAGE_SRC_RE = re.compile(r'<img\s+[^>]*src="([^"]+)"', re.IGNORECASE)

# Re-export for backward compatibility
_extract_frontmatter = extract_frontmatter
_extract_excerpt = DescriptionExtractor()._extract_excerpt

# Note: _generate_heading_id, _rewrite_image_path, and _HighlightRenderer
# are re-exported from renderers module for backward compatibility


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


class FileContentLoader:
    """Loads content files from a directory.

    This class is responsible for discovering and iterating over
    content files in a site directory. It follows the Single
    Responsibility Principle - only handles file discovery.

    Attributes:
        site_dir: Directory containing site content.
    """

    def __init__(self, site_dir: Path):
        """Initialize the content loader.

        Args:
            site_dir: Path to the site content directory.
        """
        self.site_dir = site_dir

    def iter_files(self, include_drafts: bool = False) -> list[Path]:
        """Iterate over all content files.

        Args:
            include_drafts: Whether to include draft files.

        Returns:
            List of paths to content files.
        """
        files: list[Path] = []
        for path in self.site_dir.rglob("*"):
            if path.is_dir():
                continue
            rel = path.relative_to(self.site_dir)
            parts = rel.parts
            # Skip internal directories (starting with _)
            if any(part.startswith("_") for part in parts[:-1]):
                continue
            # Skip drafts unless requested
            if rel.name.startswith("_") and not include_drafts:
                continue
            # Only include processable files
            if is_markdown(path) or is_template(path) or is_html(path):
                files.append(path)
        return files


class LayoutResolver:
    """Resolves layout templates for pages.

    This class is responsible for determining which layout template
    to use for a given page. It follows the Single Responsibility
    Principle - only handles layout resolution.

    Attributes:
        site_dir: Directory containing site content and layouts.
    """

    def __init__(self, site_dir: Path):
        """Initialize the layout resolver.

        Args:
            site_dir: Path to the site content directory.
        """
        self.site_dir = site_dir
        self.layout_dir = site_dir / "_layouts"

    def resolve(self, path: Path, folder: str) -> str:
        """Resolve the layout for a page.

        Searches for layouts in order:
        1. {folder}/{name} - Most specific
        2. {group} - Group-level layout
        3. default - Fallback

        Args:
            path: Path to the source file.
            folder: Folder containing the page.

        Returns:
            Layout name to use.
        """
        name = path.stem
        group = self._group_from_folder(folder)
        candidates: list[str] = []

        if folder:
            candidates.append(f"{folder}/{name}")
            candidates.append(group)
        else:
            candidates.append(name)
        candidates.append("default")

        for candidate in candidates:
            for suffix in (".html.jinja", ".jinja", ".html", ""):
                target = self.layout_dir / f"{candidate}{suffix}"
                if target.exists():
                    return candidate
        return "default"

    def _group_from_folder(self, folder: str) -> str:
        """Extract the group from a folder path.

        Args:
            folder: Folder path.

        Returns:
            The first component of the folder path, or empty string.
        """
        if not folder:
            return ""
        first = Path(folder).parts[0]
        return first


class UrlDeriver:
    """Derives URLs for pages.

    This class is responsible for generating URL paths for pages
    based on their location in the site structure. It follows the
    Single Responsibility Principle - only handles URL derivation.
    """

    def derive(self, rel: Path, slug: str) -> str:
        """Derive the URL for a page.

        Args:
            rel: Relative path from site directory.
            slug: URL-friendly slug.

        Returns:
            URL path for the page.
        """
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


class DefaultPageBuilder:
    """Builds Page objects from source files.

    This class coordinates the various components (renderers, extractors,
    resolvers) to build complete Page objects. It follows the Dependency
    Inversion Principle - depends on abstractions rather than concretions.

    Attributes:
        site_dir: Directory containing site content.
        renderer_registry: Registry of content renderers.
        metadata_extractor: Composite metadata extractor.
        layout_resolver: Layout resolver instance.
        url_deriver: URL deriver instance.
    """

    def __init__(
        self,
        site_dir: Path,
        renderer_registry: RendererRegistry | None = None,
        metadata_extractor: CompositeMetadataExtractor | None = None,
    ):
        """Initialize the page builder.

        Args:
            site_dir: Path to the site content directory.
            renderer_registry: Optional custom renderer registry.
            metadata_extractor: Optional custom metadata extractor.
        """
        self.site_dir = site_dir
        self.renderer_registry = renderer_registry or default_renderer_registry
        self.metadata_extractor = metadata_extractor or default_metadata_extractor
        self.layout_resolver = LayoutResolver(site_dir)
        self.url_deriver = UrlDeriver()

    def build(self, path: Path, draft: bool = False) -> Page:
        """Build a Page object from a source file.

        Args:
            path: Path to the source file.
            draft: Whether this is a draft page.

        Returns:
            Page object.
        """
        rel = path.relative_to(self.site_dir)
        folder = str(rel.parent.as_posix()) if rel.parent != Path(".") else ""
        filename = path.name
        raw_body = path.read_text(encoding="utf-8")

        # Extract metadata
        metadata = self.metadata_extractor.extract(raw_body, path)
        frontmatter = metadata.get("frontmatter", {})
        body = metadata.get("body", raw_body)

        # Get renderer and render content
        renderer = self.renderer_registry.get_renderer(path)
        if renderer:
            source_type = renderer.source_type
            render_source = strip_hashtags(body)
            content, toc = renderer.render(render_source, folder)
        else:
            source_type = "unknown"
            content = body
            toc = []

        # Resolve other properties
        layout = self.layout_resolver.resolve(path, folder)
        slug = slugify(path.stem)
        url = self.url_deriver.derive(rel, slug)
        group = self.layout_resolver._group_from_folder(folder)

        # Rewrite inline images
        content = self._rewrite_inline_images(content, folder)

        return Page(
            title=metadata.get("title", titleize(filename)),
            body=body,
            content=content,
            description=metadata.get("description", ""),
            excerpt=metadata.get("excerpt", ""),
            url=url,
            slug=slug,
            date=metadata.get("date", datetime.now()),
            tags=metadata.get("tags", []),
            draft=draft,
            layout=layout,
            group=group,
            path=path,
            folder=folder,
            filename=filename,
            source_type=source_type,
            frontmatter=frontmatter,
            toc=toc,
        )

    def _rewrite_inline_images(self, html: str, folder: str) -> str:
        """Rewrite image paths in HTML content.

        Args:
            html: HTML content.
            folder: Folder containing the page.

        Returns:
            HTML with rewritten image paths.
        """

        def repl(match: re.Match) -> str:
            src = match.group(1)
            rewritten = _rewrite_image_path(src, folder)
            return match.group(0).replace(src, rewritten)

        return IMAGE_SRC_RE.sub(repl, html)


class ContentProcessor:
    """Facade for processing content files and building Page objects.

    This class provides backward compatibility with the original API
    while internally delegating to the new SOLID-compliant components.

    Attributes:
        site_dir: Directory containing site content.
    """

    def __init__(
        self,
        site_dir: Path,
        content_loader: FileContentLoader | None = None,
        page_builder: DefaultPageBuilder | None = None,
    ):
        """Initialize the content processor.

        Args:
            site_dir: Path to the site content directory.
            content_loader: Optional custom content loader.
            page_builder: Optional custom page builder.
        """
        self.site_dir = site_dir
        self._content_loader = content_loader or FileContentLoader(site_dir)
        self._page_builder = page_builder or DefaultPageBuilder(site_dir)

    def load(self, include_drafts: bool = False) -> list[Page]:
        """Load all content files and create Page objects.

        Args:
            include_drafts: Whether to include draft pages.

        Returns:
            List of Page objects.
        """
        pages: list[Page] = []
        for path in self._content_loader.iter_files(include_drafts):
            draft = path.name.startswith("_")
            page = self._page_builder.build(path, draft=draft)
            pages.append(page)
        return pages

    # Legacy methods for backward compatibility
    def _iter_source_files(self, include_drafts: bool) -> Iterable[Path]:
        """Iterate over all source files in the site directory.

        Deprecated: Use content_loader.iter_files() instead.
        """
        return self._content_loader.iter_files(include_drafts)

    def _build_page(self, path: Path, draft: bool) -> Page:
        """Build a Page object from a source file.

        Deprecated: Use page_builder.build() instead.
        """
        return self._page_builder.build(path, draft)

    def _rewrite_inline_images(self, html: str, folder: str) -> str:
        """Rewrite image paths in HTML content.

        Deprecated: Use page_builder._rewrite_inline_images() instead.
        """
        return self._page_builder._rewrite_inline_images(html, folder)
