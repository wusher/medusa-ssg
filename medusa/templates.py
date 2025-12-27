"""Template rendering engine for Medusa.

This module uses Jinja2 to render templates and pages.
It manages template loading, global variables, and rendering of content with layouts.

Key class:
- TemplateEngine: Handles template rendering and provides context to templates.

Design principles:
- Single Responsibility: Template rendering is separate from asset resolution.
- Dependency Inversion: Engine depends on abstractions for asset resolution.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape
from markupsafe import Markup

from .asset_resolver import AssetNotFoundError, DefaultAssetPathResolver
from .collections import PageCollection, TagCollection
from .content import Heading, Page
from .utils import join_root_url

# Re-export AssetNotFoundError for backward compatibility
__all__ = ["AssetNotFoundError", "TemplateEngine", "render_toc"]


def render_toc(page: Page) -> Markup:
    """Render a table of contents as nested HTML from page headings.

    Generates properly nested `<ul><li><a href="#id">text</a></li></ul>` structure
    based on heading levels.

    Args:
        page: Page object containing the toc (list of Heading objects).

    Returns:
        Markup-safe HTML string of the nested TOC, or empty Markup if no headings.
    """
    if not page.toc:
        return Markup("")

    return _render_toc_from_headings(page.toc)


def _render_toc_from_headings(headings: list[Heading]) -> Markup:
    """Render a list of headings as nested HTML.

    Args:
        headings: List of Heading objects.

    Returns:
        Markup-safe HTML string of the nested TOC.
    """
    if not headings:
        return Markup("")

    html_parts: list[str] = []
    level_stack: list[int] = []

    for heading in headings:
        level = heading.level

        # Close nested lists if going to a shallower level
        while level_stack and level_stack[-1] > level:
            level_stack.pop()
            html_parts.append("</li></ul>")

        if level_stack and level_stack[-1] == level:
            # Same level: close previous li
            html_parts.append("</li>")
        elif not level_stack or level > level_stack[-1]:  # pragma: no branch
            # Deeper level: open a new ul
            # Note: The "else" case is unreachable due to the while loop above
            # which ensures level_stack[-1] <= level when stack is non-empty
            html_parts.append("<ul>")
            level_stack.append(level)

        # Escape text for HTML safety
        escaped_text = (
            heading.text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
        escaped_id = (
            heading.id.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

        html_parts.append(f'<li><a href="#{escaped_id}">{escaped_text}</a>')

    # Close all remaining open tags
    while level_stack:
        level_stack.pop()
        html_parts.append("</li></ul>")

    return Markup("".join(html_parts))


class TemplateEngine:
    """Template rendering engine using Jinja2.

    This class handles template rendering and provides context to templates.
    Asset path resolution is delegated to DefaultAssetPathResolver, following
    the Single Responsibility Principle.

    Attributes:
        site_dir: Directory containing templates.
        data: Global site data.
        env: Jinja2 environment.
        pages: List of all pages.
        tags: Dictionary of tags to pages.
        asset_resolver: Resolver for asset paths.
    """

    def __init__(
        self,
        site_dir: Path,
        data: dict[str, Any],
        root_url: str | None = None,
        asset_resolver: DefaultAssetPathResolver | None = None,
    ):
        """Initialize the template engine.

        Args:
            site_dir: Directory with templates.
            data: Global site data.
            root_url: Optional base URL for links.
            asset_resolver: Optional custom asset resolver.
        """
        self.site_dir = site_dir
        self.data = data
        self.root_url = (
            root_url or (data.get("root_url") if isinstance(data, dict) else "")
        ) or ""
        self.env = Environment(
            loader=FileSystemLoader(
                [
                    site_dir / "_layouts",
                    site_dir / "_partials",
                    site_dir,
                ]
            ),
            autoescape=select_autoescape(["html", "xml"]),
            enable_async=False,
        )
        self.pages: Iterable[Page] = []
        self.tags: dict[str, list[Page]] = {}

        # Initialize asset resolver with URL generator
        self.asset_resolver = asset_resolver or DefaultAssetPathResolver(site_dir)
        self.asset_resolver.set_url_generator(self._url_for)

        self._install_globals()

    def _install_globals(self) -> None:
        """Install global variables and functions in the Jinja environment."""
        self.env.globals["data"] = self.data
        self.env.globals["pages"] = self.pages
        self.env.globals["tags"] = self.tags
        self.env.globals["url_for"] = self._url_for
        self.env.globals["pygments_css"] = self._pygments_css
        self.env.globals["js_path"] = self._js_path
        self.env.globals["css_path"] = self._css_path
        self.env.globals["img_path"] = self._img_path
        self.env.globals["font_path"] = self._font_path
        self.env.globals["render_toc"] = render_toc

    @staticmethod
    def _pygments_css() -> str:
        """Return Pygments CSS styles for syntax highlighting.

        Returns:
            CSS string for the .highlight class.
        """
        try:
            from pygments.formatters import HtmlFormatter

            return HtmlFormatter().get_style_defs(".highlight")
        except ImportError:
            return ""

    def _js_path(self, name: str) -> str:
        """Return URL path for a JavaScript file.

        Delegates to the asset resolver.

        Args:
            name: Filename with or without extension.

        Returns:
            URL path like /assets/js/app.js
        """
        return self.asset_resolver.js_path(name)

    def _css_path(self, name: str) -> str:
        """Return URL path for a CSS file.

        Delegates to the asset resolver.

        Args:
            name: Filename with or without extension.

        Returns:
            URL path like /assets/css/main.css
        """
        return self.asset_resolver.css_path(name)

    def _img_path(self, name: str) -> str:
        """Return URL path for an image file.

        Delegates to the asset resolver.

        Args:
            name: Filename with or without extension.

        Returns:
            URL path like /assets/images/logo.png
        """
        return self.asset_resolver.img_path(name)

    def _font_path(self, name: str) -> str:
        """Return URL path for a font file.

        Delegates to the asset resolver.

        Args:
            name: Filename with or without extension.

        Returns:
            URL path like /assets/fonts/inter.woff2
        """
        return self.asset_resolver.font_path(name)

    def update_collections(
        self, pages: Iterable[Page], tags: dict[str, list[Page]]
    ) -> None:
        """Update the page and tag collections.

        Args:
            pages: Iterable of all pages.
            tags: Dictionary mapping tag names to page lists.
        """
        self.pages = PageCollection(pages)
        self.tags = TagCollection(tags)
        self.env.globals["pages"] = self.pages
        self.env.globals["tags"] = self.tags

    def _url_for(self, path: str) -> str:
        """Generate a URL for a path, applying root_url if configured.

        Args:
            path: Path to generate URL for.

        Returns:
            Full URL with root_url prefix if configured.
        """
        if path.startswith(("http://", "https://", "//")):
            return path
        base = self.root_url or (
            self.data.get("url", "") if isinstance(self.data, dict) else ""
        )
        if base:
            return join_root_url(base, path if path.startswith("/") else f"/{path}")
        return path if path.startswith("/") else f"/{path}"

    def render_page(self, page: Page) -> str:
        """Render a page with its layout.

        Args:
            page: Page object to render.

        Returns:
            Rendered HTML string.
        """
        context = {
            "data": self.data,
            "current_page": page,
            "frontmatter": page.frontmatter,
            "pages": self.pages,
            "tags": self.tags,
            "url_for": self._url_for,
        }
        body_html = self._render_body(page, context)
        layout_template = self._resolve_layout_template(page.layout)
        try:
            return layout_template.render(page_content=body_html, **context)
        except TemplateNotFound as exc:
            print(f"Template not found during render ({exc}); rendering body only.")
            return body_html

    def _render_body(self, page: Page, context: dict[str, Any]) -> str:
        """Render the page body.

        Args:
            page: Page object to render.
            context: Template context dictionary.

        Returns:
            Rendered body HTML.
        """
        if page.source_type == "jinja":
            template = self.env.from_string(page.content)
            return template.render(**context)
        return page.content

    def _resolve_layout_template(self, layout: str):
        """Resolve and return the layout template.

        Args:
            layout: Layout name to resolve.

        Returns:
            Jinja2 Template object.
        """
        candidates = [
            f"{layout}.html.jinja",
            f"{layout}.jinja",
            f"{layout}.html",
            layout,
        ]
        # If layout isn't "default", also try falling back to default
        if layout != "default":
            candidates.extend(
                [
                    "default.html.jinja",
                    "default.jinja",
                    "default.html",
                    "default",
                ]
            )
        for name in candidates:
            try:
                return self.env.get_template(name)
            except TemplateNotFound:
                continue
        return self.env.from_string("{{ page_content | safe }}")

    def render_string(self, template: str, context: dict[str, Any]) -> str:
        """Render a template string.

        Args:
            template: Template string to render.
            context: Variables to make available in the template.

        Returns:
            Rendered string.
        """
        tmpl = self.env.from_string(template)
        return tmpl.render(**context)
