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
from datetime import datetime
from pathlib import Path
from typing import Iterable


HASHTAG_RE = re.compile(r"#([a-zA-Z][a-zA-Z0-9]{2,}(?:/[a-zA-Z0-9]+)*)")


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
            for item in sorted([p for p in path.rglob("*") if p.is_dir()], reverse=True):
                item.rmdir()
            path.rmdir()
    path.mkdir(parents=True, exist_ok=True)


def is_internal_path(path: Path) -> bool:
    return any(part.startswith("_") for part in path.parts)


def is_markdown(path: Path) -> bool:
    return path.suffix.lower() == ".md"


def is_template(path: Path) -> bool:
    return path.suffixes[-2:] == [".html", ".jinja"] or path.suffix == ".jinja"


def limit_lines(text: str, width: int = 80) -> str:
    return "\n".join(textwrap.fill(line, width) for line in text.splitlines())


def build_tags_index(pages: Iterable) -> dict[str, list]:
    tags: dict[str, list] = {}
    for page in pages:
        for tag in page.tags:
            tags.setdefault(tag, []).append(page)
    return tags
