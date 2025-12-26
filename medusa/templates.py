"""Template rendering engine for Medusa.

This module uses Jinja2 to render templates and pages.
It manages template loading, global variables, and rendering of content with layouts.

Key class:
- TemplateEngine: Handles template rendering and provides context to templates.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape
from markupsafe import Markup

from .collections import PageCollection, TagCollection
from .content import Heading, Page
from .utils import join_root_url


class AssetNotFoundError(Exception):
    """Error raised when an asset file is not found.

    Attributes:
        asset_name: The name of the asset that was requested.
        asset_type: The type of asset (e.g., "image", "font", "js", "css").
        searched_paths: List of paths that were searched.
    """

    def __init__(
        self,
        asset_name: str,
        asset_type: str,
        searched_paths: list[Path],
    ):
        self.asset_name = asset_name
        self.asset_type = asset_type
        self.searched_paths = searched_paths
        paths_str = ", ".join(str(p) for p in searched_paths)
        super().__init__(
            f"{asset_type} asset '{asset_name}' not found. Searched: {paths_str}"
        )


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

    Attributes:
        site_dir: Directory containing templates.
        data: Global site data.
        env: Jinja2 environment.
        pages: List of all pages.
        tags: Dictionary of tags to pages.
    """

    def __init__(
        self, site_dir: Path, data: dict[str, Any], root_url: str | None = None
    ):
        """Initialize the template engine.

        Args:
            site_dir: Directory with templates.
            data: Global site data.
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
        self._install_globals()

    def _install_globals(self) -> None:
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

        Args:
            name: Filename with or without extension (e.g., "app" or "app.js").

        Returns:
            URL path like /assets/js/app.js

        Raises:
            AssetNotFoundError: If the JavaScript file doesn't exist.
        """
        if not name.endswith(".js"):
            name = f"{name}.js"
        file_path = self.site_dir.parent / "assets" / "js" / name
        if not file_path.exists():
            raise AssetNotFoundError(name, "JavaScript", [file_path])
        return self._url_for(f"/assets/js/{name}")

    def _css_path(self, name: str) -> str:
        """Return URL path for a CSS file.

        Args:
            name: Filename with or without extension (e.g., "main" or "main.css").

        Returns:
            URL path like /assets/css/main.css

        Raises:
            AssetNotFoundError: If the CSS file doesn't exist.
        """
        if not name.endswith(".css"):
            name = f"{name}.css"
        file_path = self.site_dir.parent / "assets" / "css" / name
        if not file_path.exists():
            raise AssetNotFoundError(name, "CSS", [file_path])
        return self._url_for(f"/assets/css/{name}")

    def _img_path(self, name: str) -> str:
        """Return URL path for an image file, auto-detecting extension.

        Searches for the image with extensions in order: png, jpg, jpeg, gif, svg, webp.
        If name already has an extension, validates it exists.

        Args:
            name: Filename with or without extension (e.g., "logo" or "logo.png").

        Returns:
            URL path like /assets/images/logo.png

        Raises:
            AssetNotFoundError: If no matching image file is found.
        """
        assets_dir = self.site_dir.parent / "assets" / "images"
        extensions = ("png", "jpg", "jpeg", "gif", "svg", "webp")

        # If already has a known image extension, validate it exists
        for ext in extensions:
            if name.endswith(f".{ext}"):
                file_path = assets_dir / name
                if not file_path.exists():
                    raise AssetNotFoundError(name, "image", [file_path])
                return self._url_for(f"/assets/images/{name}")

        # Auto-detect extension
        searched_paths = []
        for ext in extensions:
            file_path = assets_dir / f"{name}.{ext}"
            searched_paths.append(file_path)
            if file_path.exists():
                return self._url_for(f"/assets/images/{name}.{ext}")

        raise AssetNotFoundError(name, "image", searched_paths)

    def _font_path(self, name: str) -> str:
        """Return URL path for a font file, auto-detecting extension.

        Searches for the font with extensions in order: woff2, woff, ttf, otf, eot.
        If name already has an extension, validates it exists.

        Args:
            name: Filename with or without extension (e.g., "inter" or "inter.woff2").

        Returns:
            URL path like /assets/fonts/inter.woff2

        Raises:
            AssetNotFoundError: If no matching font file is found.
        """
        assets_dir = self.site_dir.parent / "assets" / "fonts"
        extensions = ("woff2", "woff", "ttf", "otf", "eot")

        # If already has a known font extension, validate it exists
        for ext in extensions:
            if name.endswith(f".{ext}"):
                file_path = assets_dir / name
                if not file_path.exists():
                    raise AssetNotFoundError(name, "font", [file_path])
                return self._url_for(f"/assets/fonts/{name}")

        # Auto-detect extension
        searched_paths = []
        for ext in extensions:
            file_path = assets_dir / f"{name}.{ext}"
            searched_paths.append(file_path)
            if file_path.exists():
                return self._url_for(f"/assets/fonts/{name}.{ext}")

        raise AssetNotFoundError(name, "font", searched_paths)

    def update_collections(
        self, pages: Iterable[Page], tags: dict[str, list[Page]]
    ) -> None:
        self.pages = PageCollection(pages)
        self.tags = TagCollection(tags)
        self.env.globals["pages"] = self.pages
        self.env.globals["tags"] = self.tags

    def _url_for(self, path: str) -> str:
        if path.startswith(("http://", "https://", "//")):
            return path
        # Always keep asset URLs relative to avoid cross-origin issues during dev.
        base = self.root_url or (
            self.data.get("url", "") if isinstance(self.data, dict) else ""
        )
        if base:
            return join_root_url(base, path if path.startswith("/") else f"/{path}")
        return path if path.startswith("/") else f"/{path}"

    def render_page(self, page: Page) -> str:
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
        if page.source_type == "jinja":
            template = self.env.from_string(page.content)
            return template.render(**context)
        return page.content

    def _resolve_layout_template(self, layout: str):
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
