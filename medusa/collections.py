from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, Sequence

from .content import Page
from .utils import extract_number_from_name, strip_number_prefix


class PageCollection(Sequence[Page]):
    """Lightweight helper for working with lists of Pages in templates and code."""

    def __init__(self, pages: Iterable[Page]):
        self._pages = list(pages)
        # Stable sort cache for .sorted()/latest() to avoid recomputing repeatedly
        self._sorted_cache: PageCollection | None = None

    def __iter__(self) -> Iterator[Page]:
        return iter(self._pages)

    def __len__(self) -> int:
        return len(self._pages)

    def __getitem__(self, item):
        return self._pages[item]

    def group(self, name: str) -> PageCollection:
        return PageCollection(p for p in self._pages if p.group == name)

    def with_tag(self, tag: str) -> PageCollection:
        return PageCollection(p for p in self._pages if tag in p.tags)

    def drafts(self) -> PageCollection:
        return PageCollection(p for p in self._pages if p.draft)

    def published(self) -> PageCollection:
        return PageCollection(p for p in self._pages if not p.draft)

    def sorted(self, reverse: bool = True) -> PageCollection:
        """Sort pages by date, then by number prefix, then by filename.

        Sorting order (when reverse=True, the default):
        1. Date: newest first
        2. Number: if dates are equal, by number prefix (e.g., 01-intro.md)
        3. Filename: if dates and numbers are equal, alphabetically by filename
           (excluding date and number prefixes)

        Args:
            reverse: If True (default), newest/highest first. If False, oldest/lowest first.

        Returns:
            A new PageCollection with sorted pages.
        """
        if self._sorted_cache is None or reverse is False:

            def sort_key(p: Page):
                number = extract_number_from_name(p.path.stem)
                # Use 0 if no number (so numbered files come after non-numbered when ascending)
                # Use float('inf') for reverse so non-numbered come last
                num_key = number if number is not None else (0 if not reverse else float("inf"))
                name_key = strip_number_prefix(p.path.stem).lower()
                return (p.date, num_key, name_key)

            sorted_pages = sorted(self._pages, key=sort_key, reverse=reverse)
            if reverse:
                self._sorted_cache = PageCollection(sorted_pages)
            return PageCollection(sorted_pages)
        return self._sorted_cache

    def latest(self, count: int = 5) -> PageCollection:
        return PageCollection(self.sorted()[:count])

    def __repr__(self) -> str:  # pragma: no cover - for debugging
        return f"PageCollection({len(self._pages)} pages)"


class TagCollection(Mapping[str, PageCollection]):
    """Mapping of tag name to PageCollection with convenience helpers."""

    def __init__(self, mapping: dict[str, Iterable[Page]]):
        self._mapping = {k: PageCollection(v) for k, v in mapping.items()}

    def __getitem__(self, key: str) -> PageCollection:
        return self._mapping[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._mapping)

    def __len__(self) -> int:
        return len(self._mapping)

    def get(self, key: str, default=None):
        return self._mapping.get(key, default)

    def items(self):
        return self._mapping.items()

    def keys(self):
        return self._mapping.keys()

    def values(self):
        return self._mapping.values()

    def __repr__(self) -> str:  # pragma: no cover - for debugging
        return f"TagCollection({len(self._mapping)} tags)"
