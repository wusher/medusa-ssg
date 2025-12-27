"""Feed generation for Medusa.

This module provides functionality for generating various feed formats
(sitemap.xml, RSS) from site content. Following the Single Responsibility
Principle, feed generation is separate from build orchestration.

The module uses a protocol-based design to allow easy extension with
new feed formats (Open/Closed Principle).

Classes:
    FeedGenerator: Protocol for feed generators.
    SitemapGenerator: Generates sitemap.xml files.
    RSSGenerator: Generates RSS feed files.
    FeedRegistry: Registry for managing feed generators.

Functions:
    create_default_feed_registry: Create a registry with default generators.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .content import Page


class FeedGenerator(ABC):
    """Abstract base class for feed generators.

    This class defines the interface for all feed generators.
    Subclasses implement specific feed formats (sitemap, RSS, Atom, etc.).

    Following the Open/Closed Principle, new feed formats can be added
    by creating new subclasses without modifying existing code.
    """

    @property
    @abstractmethod
    def filename(self) -> str:
        """Return the output filename for this feed.

        Returns:
            Filename such as 'sitemap.xml' or 'rss.xml'.
        """
        ...

    @abstractmethod
    def generate(
        self,
        pages: Iterable[Page],
        data: dict[str, Any],
    ) -> str | None:
        """Generate feed content from pages.

        Args:
            pages: Iterable of Page objects to include in the feed.
            data: Site data dictionary containing configuration like base URL.

        Returns:
            Feed content as a string, or None if feed cannot be generated
            (e.g., missing required configuration).
        """
        ...

    def write(
        self,
        output_dir: Path,
        pages: Iterable[Page],
        data: dict[str, Any],
    ) -> bool:
        """Generate and write feed to the output directory.

        Args:
            output_dir: Directory to write the feed file to.
            pages: Iterable of Page objects to include in the feed.
            data: Site data dictionary.

        Returns:
            True if the feed was written, False if skipped.
        """
        content = self.generate(pages, data)
        if content is None:
            return False
        output_path = output_dir / self.filename
        output_path.write_text(content, encoding="utf-8")
        return True


class SitemapGenerator(FeedGenerator):
    """Generates sitemap.xml for search engine indexing.

    Creates a sitemap following the sitemaps.org protocol, listing
    all pages with their URLs and last modification dates.

    Requires 'url' in site data to generate absolute URLs.
    """

    @property
    def filename(self) -> str:
        """Return sitemap filename."""
        return "sitemap.xml"

    def generate(
        self,
        pages: Iterable[Page],
        data: dict[str, Any],
    ) -> str | None:
        """Generate sitemap.xml content.

        Args:
            pages: Iterable of Page objects.
            data: Site data containing 'url' for base URL.

        Returns:
            Sitemap XML content, or None if no base URL configured.
        """
        base_url = str(data.get("url", "")).rstrip("/")
        if not base_url:
            return None

        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        ]
        for page in pages:
            full_url = f"{base_url}{page.url}"
            lastmod = page.date.strftime("%Y-%m-%d")
            lines.append(
                f"  <url><loc>{full_url}</loc><lastmod>{lastmod}</lastmod></url>"
            )
        lines.append("</urlset>")
        return "\n".join(lines)


class RSSGenerator(FeedGenerator):
    """Generates RSS 2.0 feed for content syndication.

    Creates an RSS feed with all pages sorted by date (newest first).

    Requires 'url' in site data to generate absolute URLs.
    Uses 'title' from site data for the feed title.
    """

    @property
    def filename(self) -> str:
        """Return RSS filename."""
        return "rss.xml"

    def generate(
        self,
        pages: Iterable[Page],
        data: dict[str, Any],
    ) -> str | None:
        """Generate RSS feed content.

        Args:
            pages: Iterable of Page objects.
            data: Site data containing 'url' and optionally 'title'.

        Returns:
            RSS XML content, or None if no base URL configured.
        """
        base_url = str(data.get("url", "")).rstrip("/")
        title = data.get("title", "Medusa Feed")
        if not base_url:
            return None

        items = []
        for page in sorted(pages, key=lambda p: p.date, reverse=True):
            link = f"{base_url}{page.url}"
            pub_date = page.date.strftime("%a, %d %b %Y %H:%M:%S +0000")
            description = page.description or page.title
            items.append(
                f"<item><title>{page.title}</title><link>{link}</link>"
                f"<description>{description}</description>"
                f"<pubDate>{pub_date}</pubDate></item>"
            )

        build_date = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
        rss = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<rss version="2.0"><channel>',
            f"<title>{title}</title>",
            f"<link>{base_url}</link>",
            f"<lastBuildDate>{build_date}</lastBuildDate>",
        ]
        rss.extend(items)
        rss.append("</channel></rss>")
        return "\n".join(rss)


class FeedRegistry:
    """Registry for managing feed generators.

    This registry allows registering multiple feed generators and
    running them all during the build process. Follows the Open/Closed
    Principle by allowing new feed types to be added without modification.

    Attributes:
        _generators: List of registered feed generators.
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._generators: list[FeedGenerator] = []

    def register(self, generator: FeedGenerator) -> None:
        """Register a feed generator.

        Args:
            generator: Feed generator to register.
        """
        self._generators.append(generator)

    def generate_all(
        self,
        output_dir: Path,
        pages: Iterable[Page],
        data: dict[str, Any],
    ) -> list[str]:
        """Generate all registered feeds.

        Args:
            output_dir: Directory to write feed files to.
            pages: Iterable of Page objects.
            data: Site data dictionary.

        Returns:
            List of filenames that were generated.
        """
        # Convert to list to allow multiple iterations
        pages_list = list(pages)
        generated = []
        for generator in self._generators:
            if generator.write(output_dir, pages_list, data):
                generated.append(generator.filename)
        return generated


def create_default_feed_registry() -> FeedRegistry:
    """Create a registry with default feed generators.

    Returns:
        FeedRegistry configured with sitemap and RSS generators.
    """
    registry = FeedRegistry()
    registry.register(SitemapGenerator())
    registry.register(RSSGenerator())
    return registry
