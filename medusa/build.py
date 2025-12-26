"""Site building functionality for Medusa.

This module contains the core logic for building a static site from source files.
It loads configuration and data, processes content, renders templates, and generates output files.

Key functions:
- build_site: Main function to build the entire site.
- load_config: Loads site configuration from medusa.yaml.
- load_data: Loads site data from YAML files in the data directory.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from jinja2 import TemplateSyntaxError

from .assets import AssetPipeline
from .content import ContentProcessor, Page
from .templates import TemplateEngine
from .utils import absolutize_html_urls, build_tags_index, ensure_clean_dir


class BuildError(Exception):
    """Error during site build with file context.

    Attributes:
        source_path: Path to the source file that caused the error.
        message: Human-readable error message.
        original_error: The original exception that was caught.
    """

    def __init__(
        self,
        source_path: Path,
        message: str,
        original_error: Exception | None = None,
    ):
        self.source_path = source_path
        self.message = message
        self.original_error = original_error
        super().__init__(f"{source_path}: {message}")


DEFAULT_CONFIG = {
    "output_dir": "output",
    "port": 4000,
    "root_url": "",
}


@dataclass
class BuildResult:
    """Result of a site build operation.

    Attributes:
        pages: List of all pages in the site.
        output_dir: Directory where the site was built.
        data: Global site data dictionary.
    """

    pages: list[Page]
    output_dir: Path
    data: dict[str, Any]


def load_config(project_root: Path) -> dict[str, Any]:
    """Load site configuration from medusa.yaml.

    Args:
        project_root: Root directory of the project.

    Returns:
        Dictionary containing configuration values, with defaults applied.
    """
    config_path = project_root / "medusa.yaml"
    config = DEFAULT_CONFIG.copy()
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
            if isinstance(loaded, dict):
                config.update(loaded)
    return config


def load_data(project_root: Path) -> dict[str, Any]:
    """Load site data from YAML files in the data directory.

    Args:
        project_root: Root directory of the project.

    Returns:
        Dictionary containing merged data from all YAML files.
    """
    data_dir = project_root / "data"
    data: dict[str, Any] = {}
    if not data_dir.exists():
        return data
    for path in sorted(data_dir.glob("*.yaml")):
        with open(path, encoding="utf-8") as f:
            payload = yaml.safe_load(f) or {}
        if not isinstance(payload, dict):
            continue
        if path.name == "site.yaml":
            data.update(payload)
        else:
            data[path.stem] = payload
    return data


def build_site(
    project_root: Path,
    include_drafts: bool = False,
    root_url: str | None = None,
    clean_output: bool = True,
    output_dir_override: Path | None = None,
) -> BuildResult:
    """Build the entire static site.

    Args:
        project_root: Root directory of the project.
        include_drafts: Whether to include draft pages (starting with _).
        root_url: Optional base URL to absolutize links with.
        clean_output: Whether to wipe the output directory before building.
        output_dir_override: Optional path to write the build output instead of config output_dir.

    Returns:
        BuildResult containing all pages, output directory, and site data.
    """
    config = load_config(project_root)
    if root_url is not None:
        config["root_url"] = root_url
    output_dir = output_dir_override or (
        project_root / config.get("output_dir", "output")
    )
    if clean_output:
        ensure_clean_dir(output_dir)
    else:
        output_dir.mkdir(parents=True, exist_ok=True)

    data = load_data(project_root)
    resolved_root = str(config.get("root_url") or "")
    if isinstance(data, dict) and resolved_root:
        data.setdefault("root_url", resolved_root)
    site_dir = project_root / "site"
    if not site_dir.exists():
        raise FileNotFoundError(f"Expected site directory at {site_dir}")
    pages = ContentProcessor(site_dir).load(include_drafts=include_drafts)
    tags = build_tags_index(pages)

    engine = TemplateEngine(site_dir, data, root_url=resolved_root)
    engine.update_collections(pages, tags)
    for page in pages:
        try:
            rendered = engine.render_page(page)
        except TemplateSyntaxError as exc:
            raise BuildError(
                page.path,
                f"Template syntax error on line {exc.lineno}: {exc.message}",
                exc,
            ) from exc
        except Exception as exc:
            raise BuildError(
                page.path,
                _format_error_message(exc),
                exc,
            ) from exc
        if resolved_root:
            rendered = absolutize_html_urls(rendered, resolved_root)
        _write_page(output_dir, page, rendered)

    AssetPipeline(project_root, output_dir).run()
    _write_sitemap(output_dir, data, pages)
    _write_rss(output_dir, data, pages)
    return BuildResult(pages=pages, output_dir=output_dir, data=data)


def _format_error_message(exc: Exception) -> str:
    """Format an exception into a user-friendly error message.

    Args:
        exc: The exception to format.

    Returns:
        A human-readable error message.
    """
    error_type = type(exc).__name__
    error_msg = str(exc)

    # Handle common Jinja2/template errors
    if error_type == "UndefinedError":
        return f"Undefined variable: {error_msg}"
    if error_type == "TypeError":
        return f"Type error: {error_msg}"
    if error_type == "AttributeError":
        return f"Attribute error: {error_msg}"

    return f"{error_type}: {error_msg}"


def _write_page(output_dir: Path, page: Page, rendered: str) -> None:
    """Write a rendered page to the output directory.

    Args:
        output_dir: Base output directory.
        page: Page object containing metadata.
        rendered: Rendered HTML content.
    """
    url_path = page.url.strip("/")
    target_dir = output_dir / url_path
    target_dir.mkdir(parents=True, exist_ok=True)
    html_path = target_dir / "index.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(rendered)


def _write_sitemap(
    output_dir: Path, data: dict[str, Any], pages: Iterable[Page]
) -> None:
    """Generate and write sitemap.xml.

    Args:
        output_dir: Output directory for the sitemap.
        data: Site data dictionary.
        pages: Iterable of all pages.
    """
    base_url = str(data.get("url", "")).rstrip("/")
    if not base_url:
        return
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for page in pages:
        full_url = f"{base_url}{page.url}"
        lastmod = page.date.strftime("%Y-%m-%d")
        lines.append(f"  <url><loc>{full_url}</loc><lastmod>{lastmod}</lastmod></url>")
    lines.append("</urlset>")
    (output_dir / "sitemap.xml").write_text("\n".join(lines), encoding="utf-8")


def _write_rss(output_dir: Path, data: dict[str, Any], pages: Iterable[Page]) -> None:
    """Generate and write rss.xml feed.

    Args:
        output_dir: Output directory for the RSS feed.
        data: Site data dictionary.
        pages: Iterable of all pages.
    """
    base_url = str(data.get("url", "")).rstrip("/")
    title = data.get("title", "Medusa Feed")
    if not base_url:
        return
    items = []
    for page in sorted(pages, key=lambda p: p.date, reverse=True):
        link = f"{base_url}{page.url}"
        pub_date = page.date.strftime("%a, %d %b %Y %H:%M:%S +0000")
        description = page.description or page.title
        items.append(
            f"<item><title>{page.title}</title><link>{link}</link><description>{description}</description><pubDate>{pub_date}</pubDate></item>"
        )
    rss = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0"><channel>',
        f"<title>{title}</title>",
        f"<link>{base_url}</link>",
        f"<lastBuildDate>{datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S +0000')}</lastBuildDate>",
    ]
    rss.extend(items)
    rss.append("</channel></rss>")
    (output_dir / "rss.xml").write_text("\n".join(rss), encoding="utf-8")
