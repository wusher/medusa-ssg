"""Utility functions for Medusa.

This module contains various utility functions used throughout the Medusa codebase.
These include string processing, path handling, date extraction, and content manipulation.

Key functions:
    slugify: Convert filenames to URL slugs.
    titleize: Convert filenames to human-readable titles.
    extract_tags: Extract hashtags from text.
    build_tags_index: Build index of pages by tags.
    extract_date_from_name: Extract date from filename prefix.
    is_markdown: Check if a path is a Markdown file.
    is_template: Check if a path is a Jinja template.
    is_html: Check if a path is a plain HTML file.
    ensure_clean_dir: Ensure a directory exists and is empty.

Note:
    HTML-related utilities (escape_html, absolutize_html_urls, join_root_url)
    are now in html_utils.py but re-exported here for backward compatibility.
"""

from __future__ import annotations

import re
import shutil
import textwrap
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

# Re-export from html_utils for backward compatibility
from .html_utils import absolutize_html_urls, join_root_url  # noqa: F401

HASHTAG_RE = re.compile(r"#([a-zA-Z][a-zA-Z0-9]{2,}(?:/[a-zA-Z0-9]+)*)")


def slugify(name: str) -> str:
    """Convert filename (without extension) to slug, dropping date prefix.

    Args:
        name: Filename stem.

    Returns:
        URL-friendly slug.
    """
    cleaned = name
    if "-" in cleaned:
        parts = cleaned.split("-")
        if len(parts) >= 4 and all(p.isdigit() for p in parts[:3]):
            cleaned = "-".join(parts[3:])
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", cleaned)
    cleaned = cleaned.strip("-").lower()
    return cleaned or "index"


def titleize(filename: str) -> str:
    """Convert a filename to a human-readable title.

    Removes date prefixes (YYYY-MM-DD), replaces hyphens and underscores
    with spaces, and capitalizes each word.

    Args:
        filename: Filename with or without extension.

    Returns:
        Human-readable title string.

    Examples:
        >>> titleize("2024-01-15-hello-world.md")
        'Hello World'

        >>> titleize("getting-started.md")
        'Getting Started'
    """
    base = Path(filename).stem
    if "-" in base:
        parts = base.split("-")
        if len(parts) >= 4 and all(p.isdigit() for p in parts[:3]):
            base = "-".join(parts[3:])
    words = re.split(r"[\s\-_]+", base)
    return " ".join(word.capitalize() for word in words if word) or "Untitled"


def extract_date_from_name(name: str) -> datetime | None:
    """Extract a date from a filename with YYYY-MM-DD prefix.

    Args:
        name: Filename stem (without extension).

    Returns:
        datetime object if a valid date prefix is found, None otherwise.

    Examples:
        >>> extract_date_from_name("2024-01-15-hello-world")
        datetime(2024, 1, 15, 0, 0)

        >>> extract_date_from_name("hello-world")
        None
    """
    parts = name.split("-")
    if len(parts) >= 3 and all(p.isdigit() for p in parts[:3]):
        try:
            return datetime(int(parts[0]), int(parts[1]), int(parts[2]))
        except ValueError:
            return None
    return None


def extract_tags(text: str) -> list[str]:
    """Extract hashtags from text content.

    Finds hashtags matching the pattern #word where word starts with
    a letter and is at least 3 characters. Hierarchical tags like
    #topic/subtopic are also supported.

    Args:
        text: Text content to search for hashtags.

    Returns:
        List of unique tag names (without the # symbol).

    Examples:
        >>> extract_tags("Hello #world, this is #python code")
        ['world', 'python']
    """
    tags = HASHTAG_RE.findall(text)
    seen = []
    for tag in tags:
        if tag not in seen:
            seen.append(tag)
    return seen


def strip_hashtags(text: str) -> str:
    """Remove hashtag symbols from text, keeping the tag words.

    Args:
        text: Text containing hashtags.

    Returns:
        Text with # symbols removed but tag words preserved.

    Examples:
        >>> strip_hashtags("Hello #world")
        'Hello world'
    """
    return HASHTAG_RE.sub(lambda m: m.group(1), text)


def first_paragraph(text: str, limit: int = 160) -> str:
    """Extract and clean the first paragraph from text.

    Strips leading # (headers), HTML tags, and Jinja syntax.
    Collapses whitespace and truncates to the specified limit.

    Args:
        text: Text content to extract from.
        limit: Maximum character length of result.

    Returns:
        Cleaned first paragraph, truncated to limit characters.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return ""
    para = paragraphs[0].lstrip("# ").strip()
    # Strip HTML tags and Jinja syntax
    para = re.sub(r"<[^>]+>", "", para)
    para = re.sub(r"\{[%#{].*?[%#}]\}", "", para)
    collapsed = " ".join(para.split())
    return collapsed[:limit]


def ensure_clean_dir(path: Path) -> None:
    """Ensure a directory exists and is empty.

    If the directory exists, removes all contents. Creates the
    directory if it doesn't exist.

    Args:
        path: Directory path to clean or create.
    """
    if path.exists():
        shutil.rmtree(str(path), ignore_errors=True)
        if path.exists():
            # Fallback for stubborn directories
            for item in path.rglob("*"):
                if item.is_file():
                    item.unlink()
            for item in sorted(
                [p for p in path.rglob("*") if p.is_dir()], reverse=True
            ):
                item.rmdir()
            path.rmdir()
    path.mkdir(parents=True, exist_ok=True)


def is_internal_path(path: Path) -> bool:
    """Check if a path is internal (contains components starting with _).

    Internal paths include layouts, partials, and draft files.

    Args:
        path: Path to check.

    Returns:
        True if any path component starts with underscore.
    """
    return any(part.startswith("_") for part in path.parts)


def is_markdown(path: Path) -> bool:
    """Check if a path is a Markdown file.

    Args:
        path: Path to check.

    Returns:
        True if the file has .md extension (case-insensitive).
    """
    return path.suffix.lower() == ".md"


def is_template(path: Path) -> bool:
    """Check if a path is a Jinja template file.

    Matches both .jinja and .html.jinja extensions.

    Args:
        path: Path to check.

    Returns:
        True if the file is a Jinja template.
    """
    return path.suffixes[-2:] == [".html", ".jinja"] or path.suffix == ".jinja"


def is_html(path: Path) -> bool:
    """Check if a path is a plain HTML file (not a Jinja template).

    Args:
        path: Path to check.

    Returns:
        True if the file has .html extension but not .html.jinja.
    """
    return path.suffix.lower() == ".html" and not is_template(path)


def extract_number_from_name(name: str) -> int | None:
    """Extract a leading number from a filename for sorting.

    Handles filenames like "01-intro.md", "2-getting-started.md", etc.
    If the filename has a date prefix, extracts number after the date.

    Args:
        name: Filename stem (without extension).

    Returns:
        The extracted number, or None if no number found.
    """
    parts = name.split("-")

    # Check if starts with date (YYYY-MM-DD-)
    if len(parts) >= 4 and all(p.isdigit() for p in parts[:3]):
        # Date prefix exists, look for number after date
        if len(parts) > 3 and parts[3].isdigit():
            return int(parts[3])
        return None

    # No date prefix, check for leading number
    if parts and parts[0].isdigit():
        return int(parts[0])

    return None


def strip_number_prefix(name: str) -> str:
    """Strip date and number prefixes from filename for sorting comparison.

    Args:
        name: Filename stem (without extension).

    Returns:
        Filename with date and number prefixes removed.
    """
    parts = name.split("-")

    # Check if starts with date (YYYY-MM-DD-)
    if len(parts) >= 4 and all(p.isdigit() for p in parts[:3]):
        # Strip date
        parts = parts[3:]
        # Also strip number after date if present
        if parts and parts[0].isdigit():
            parts = parts[1:]
    elif parts and parts[0].isdigit():
        # Strip leading number
        parts = parts[1:]

    return "-".join(parts) if parts else name


def limit_lines(text: str, width: int = 80) -> str:
    """Wrap text to a maximum line width.

    Wraps each line of text to the specified width using textwrap.

    Args:
        text: Text to wrap.
        width: Maximum line width.

    Returns:
        Text with lines wrapped to the specified width.
    """
    return "\n".join(textwrap.fill(line, width) for line in text.splitlines())


def build_tags_index(pages: Iterable) -> dict[str, list]:
    """Build an index mapping tags to lists of pages containing that tag.

    Args:
        pages: Iterable of Page objects with a 'tags' attribute.

    Returns:
        Dictionary mapping tag names to lists of pages.
    """
    tags: dict[str, list] = {}
    for page in pages:
        for tag in page.tags:
            tags.setdefault(tag, []).append(page)
    return tags
