"""Template rendering engine for Medusa.

This module uses Jinja2 to render templates and pages.
It manages template loading, global variables, and rendering of content with layouts.

Key class:
- TemplateEngine: Handles template rendering and provides context to templates.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape

from .content import Page
from .collections import PageCollection, TagCollection
from .utils import join_root_url


class TemplateEngine:
    """Template rendering engine using Jinja2.

    Attributes:
        site_dir: Directory containing templates.
        data: Global site data.
        env: Jinja2 environment.
        pages: List of all pages.
        tags: Dictionary of tags to pages.
    """

    def __init__(self, site_dir: Path, data: dict[str, Any], root_url: str | None = None):
        """Initialize the template engine.

        Args:
            site_dir: Directory with templates.
            data: Global site data.
        """
        self.site_dir = site_dir
        self.data = data
        self.root_url = (root_url or (data.get("root_url") if isinstance(data, dict) else "")) or ""
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
        base = self.root_url or (self.data.get("url", "") if isinstance(self.data, dict) else "")
        if base:
            return join_root_url(base, path if path.startswith("/") else f"/{path}")
        return path if path.startswith("/") else f"/{path}"

    def render_page(self, page: Page) -> str:
        context = {
            "data": self.data,
            "current_page": page,
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
            candidates.extend([
                "default.html.jinja",
                "default.jinja",
                "default.html",
                "default",
            ])
        for name in candidates:
            try:
                return self.env.get_template(name)
            except TemplateNotFound:
                continue
        return self.env.from_string("{{ page_content | safe }}")
