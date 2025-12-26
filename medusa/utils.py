"""Utility functions for Medusa.

This module contains various utility functions used throughout the Medusa codebase.
These include string processing, path handling, date extraction, and content manipulation.

Key functions:
- slugify: Convert filenames to URL slugs.
- titleize: Convert filenames to human-readable titles.
- extract_tags: Extract hashtags from text.
- build_tags_index: Build index of pages by tags.
"""

from __future__ import annotations

import re
import shutil
import textwrap
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

HASHTAG_RE = re.compile(r"#([a-zA-Z][a-zA-Z0-9]{2,}(?:/[a-zA-Z0-9]+)*)")
_URL_ATTR_RE = re.compile(
    r'(?P<prefix>\b(?:href|src|action)=["\'])(?P<url>[^"\']+)(?P<suffix>["\'])'
)
_URL_SKIP_PREFIXES = (
    "http://",
    "https://",
    "//",
    "mailto:",
    "tel:",
    "#",
    "javascript:",
)



def slugify(name: str) -> str:
    """Convert filename (without extension) to slug, dropping date and layout suffixes.

    Args:
        name: Filename stem.

    Returns:
        URL-friendly slug.
    """
    cleaned = name
    if "[" in cleaned and "]" in cleaned:
        cleaned = cleaned.split("[", 1)[0]
    if "-" in cleaned:
        parts = cleaned.split("-")
        if len(parts) >= 4 and all(p.isdigit() for p in parts[:3]):
            cleaned = "-".join(parts[3:])
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", cleaned)
    cleaned = cleaned.strip("-").lower()
    return cleaned or "index"


def titleize(filename: str) -> str:
    base = Path(filename).stem
    if "[" in base and "]" in base:
        base = base.split("[", 1)[0]
    if "-" in base:
        parts = base.split("-")
        if len(parts) >= 4 and all(p.isdigit() for p in parts[:3]):
            base = "-".join(parts[3:])
    words = re.split(r"[\s\-_]+", base)
    return " ".join(word.capitalize() for word in words if word) or "Untitled"


def extract_date_from_name(name: str) -> datetime | None:
    parts = name.split("-")
    if len(parts) >= 3 and all(p.isdigit() for p in parts[:3]):
        try:
            return datetime(int(parts[0]), int(parts[1]), int(parts[2]))
        except ValueError:
            return None
    return None


def extract_tags(text: str) -> list[str]:
    tags = HASHTAG_RE.findall(text)
    seen = []
    for tag in tags:
        if tag not in seen:
            seen.append(tag)
    return seen


def strip_hashtags(text: str) -> str:
    return HASHTAG_RE.sub(lambda m: m.group(1), text)


def first_paragraph(text: str, limit: int = 160) -> str:
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
    return any(part.startswith("_") for part in path.parts)


def is_markdown(path: Path) -> bool:
    return path.suffix.lower() == ".md"


def is_template(path: Path) -> bool:
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
    # Strip layout suffix if present
    if "[" in name and "]" in name:
        name = name.split("[", 1)[0]

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
    # Strip layout suffix if present
    if "[" in name and "]" in name:
        name = name.split("[", 1)[0]

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
    return "\n".join(textwrap.fill(line, width) for line in text.splitlines())


def build_tags_index(pages: Iterable) -> dict[str, list]:
    tags: dict[str, list] = {}
    for page in pages:
        for tag in page.tags:
            tags.setdefault(tag, []).append(page)
    return tags


def join_root_url(root_url: str, path: str) -> str:
    """Safely join a root URL and a path, avoiding double slashes.

    Args:
        root_url: Base URL (e.g., https://example.com/blog).
        path: Path beginning with or without a leading slash.
    """
    if not root_url:
        return path
    base = root_url.rstrip("/")
    suffix = path if path.startswith("/") else f"/{path}"
    return f"{base}{suffix}"


def absolutize_html_urls(html: str, root_url: str) -> str:
    """Rewrite root-relative URLs in HTML to absolute URLs using root_url."""
    if not root_url:
        return html

    def repl(match: re.Match) -> str:
        url = match.group("url")
        if not url or url.startswith(_URL_SKIP_PREFIXES):
            return match.group(0)
        absolute = join_root_url(root_url, url)
        return f"{match.group('prefix')}{absolute}{match.group('suffix')}"

    return _URL_ATTR_RE.sub(repl, html)
