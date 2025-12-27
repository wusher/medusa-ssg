"""Metadata extractors for Medusa.

This module contains implementations of the MetadataExtractor protocol.
Each extractor handles a single type of metadata, following the
Single Responsibility Principle (SRP).

Key classes:
- TitleExtractor: Extracts title from content or filename.
- TagExtractor: Extracts hashtags from content.
- DateExtractor: Extracts date from filename or file metadata.
- DescriptionExtractor: Extracts description/excerpt from content.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from .utils import (
    extract_date_from_name,
    extract_tags,
    first_paragraph,
    strip_hashtags,
    titleize,
)

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def extract_frontmatter(text: str) -> tuple[dict[str, Any], str]:
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


class TitleExtractor:
    """Extracts title from content or filename.

    Looks for a level-1 heading (# Title) in the content,
    falling back to titleizing the filename.
    """

    def extract(self, content: str, path: Path) -> dict[str, Any]:
        """Extract title from content.

        Args:
            content: Source content.
            path: Path to the source file.

        Returns:
            Dictionary with 'title' key.
        """
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                return {"title": stripped.lstrip("# ").strip()}
        return {"title": titleize(path.name)}


class TagExtractor:
    """Extracts hashtags from content.

    Finds all #hashtag patterns in the content.
    """

    def extract(self, content: str, path: Path) -> dict[str, Any]:
        """Extract tags from content.

        Args:
            content: Source content.
            path: Path to the source file (unused).

        Returns:
            Dictionary with 'tags' key containing list of tags.
        """
        return {"tags": extract_tags(content)}


class DateExtractor:
    """Extracts date from filename or file metadata.

    Looks for YYYY-MM-DD prefix in filename, falling back
    to file modification time.
    """

    def extract(self, content: str, path: Path) -> dict[str, Any]:
        """Extract date from filename or file.

        Args:
            content: Source content (unused).
            path: Path to the source file.

        Returns:
            Dictionary with 'date' key.
        """
        date = extract_date_from_name(path.stem)
        if date is None:
            date = datetime.fromtimestamp(path.stat().st_mtime)
        return {"date": date}


class DescriptionExtractor:
    """Extracts description and excerpt from content.

    Gets the first paragraph for description (truncated to 160 chars)
    and full first paragraph as excerpt for Markdown files.
    """

    def extract(self, content: str, path: Path) -> dict[str, Any]:
        """Extract description and excerpt from content.

        Args:
            content: Source content.
            path: Path to the source file.

        Returns:
            Dictionary with 'description' and 'excerpt' keys.
        """
        cleaned = strip_hashtags(content)
        description = first_paragraph(cleaned)
        excerpt = self._extract_excerpt(cleaned) if path.suffix.lower() == ".md" else ""
        return {"description": description, "excerpt": excerpt}

    def _extract_excerpt(self, text: str) -> str:
        """Extract the first paragraph from markdown text.

        Skips the title heading and returns the first actual paragraph.

        Args:
            text: Markdown text content.

        Returns:
            The first paragraph as plain text.
        """
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        for para in paragraphs:
            if para.startswith("#"):
                continue
            if para.startswith(("![", "```", "---")):
                continue
            cleaned = " ".join(para.split())
            return cleaned
        return ""


class FrontmatterExtractor:
    """Extracts YAML frontmatter from content.

    Parses YAML frontmatter at the beginning of the file
    (between --- markers).
    """

    def extract(self, content: str, path: Path) -> dict[str, Any]:
        """Extract frontmatter from content.

        Args:
            content: Source content with potential frontmatter.
            path: Path to the source file (unused).

        Returns:
            Dictionary with 'frontmatter' key and 'body' key.
        """
        frontmatter, body = extract_frontmatter(content)
        return {"frontmatter": frontmatter, "body": body}


class CompositeMetadataExtractor:
    """Combines multiple metadata extractors.

    This class aggregates multiple extractors and runs them
    all on the content, merging their results. This follows
    the Composite pattern and maintains SRP for each extractor.
    """

    def __init__(self, extractors: list | None = None):
        """Initialize with a list of extractors.

        Args:
            extractors: List of MetadataExtractor implementations.
                       If None, uses default extractors.
        """
        if extractors is None:
            self._extractors = [
                FrontmatterExtractor(),
                TitleExtractor(),
                TagExtractor(),
                DateExtractor(),
                DescriptionExtractor(),
            ]
        else:
            self._extractors = list(extractors)

    def add_extractor(self, extractor) -> None:
        """Add an extractor to the composite.

        Args:
            extractor: A MetadataExtractor implementation.
        """
        self._extractors.append(extractor)

    def extract(self, content: str, path: Path) -> dict[str, Any]:
        """Extract all metadata from content.

        Runs all registered extractors and merges their results.
        Later extractors can override earlier ones.

        Args:
            content: Source content.
            path: Path to the source file.

        Returns:
            Dictionary with all extracted metadata.
        """
        result: dict[str, Any] = {}
        for extractor in self._extractors:
            extracted = extractor.extract(content, path)
            result.update(extracted)
        return result


# Default composite extractor instance
default_metadata_extractor = CompositeMetadataExtractor()
