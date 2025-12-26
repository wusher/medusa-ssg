from datetime import datetime
from pathlib import Path

from medusa.collections import PageCollection, TagCollection


class FakePage:
    def __init__(self, title, group="", date=None, tags=None, draft=False, filename=None):
        self.title = title
        self.group = group
        self.date = date or datetime(2024, 1, 1)
        self.tags = tags or []
        self.draft = draft
        # Create a fake path for sorting tests
        self.path = Path(filename if filename else f"{title.lower().replace(' ', '-')}.md")


def test_page_collection_filters_and_latest():
    pages = PageCollection(
        [
            FakePage("A", group="posts", date=datetime(2024, 1, 2), filename="a.md"),
            FakePage("B", group="posts", date=datetime(2024, 1, 3), draft=True, filename="b.md"),
            FakePage("C", group="docs", date=datetime(2024, 1, 1), tags=["python"], filename="c.md"),
        ]
    )
    assert len(pages) == 3
    posts = pages.group("posts")
    assert [p.title for p in posts] == ["A", "B"]
    published = pages.published()
    assert [p.title for p in published] == ["A", "C"]
    drafts = pages.drafts()
    assert [p.title for p in drafts] == ["B"]
    latest = pages.latest(1)
    assert latest[0].title == "B"
    ascending = pages.sorted(reverse=False)
    assert [p.title for p in ascending] == ["C", "A", "B"]
    # cached descending branch
    desc_first = pages.sorted()
    desc_second = pages.sorted()
    assert desc_first[0].title == "B"
    assert desc_second[0].title == "B"
    assert pages.with_tag("python")[0].title == "C"


def test_sorting_by_date_number_filename():
    """Test that sorting uses date, then number, then filename."""
    # Same date, different numbers
    pages = PageCollection(
        [
            FakePage("Third", date=datetime(2024, 1, 1), filename="03-third.md"),
            FakePage("First", date=datetime(2024, 1, 1), filename="01-first.md"),
            FakePage("Second", date=datetime(2024, 1, 1), filename="02-second.md"),
        ]
    )
    # Descending: highest number first
    sorted_desc = pages.sorted(reverse=True)
    assert [p.title for p in sorted_desc] == ["Third", "Second", "First"]

    # Ascending: lowest number first
    sorted_asc = pages.sorted(reverse=False)
    assert [p.title for p in sorted_asc] == ["First", "Second", "Third"]


def test_sorting_by_filename_when_no_numbers():
    """Test that pages without numbers sort alphabetically by filename."""
    pages = PageCollection(
        [
            FakePage("Zebra", date=datetime(2024, 1, 1), filename="zebra.md"),
            FakePage("Apple", date=datetime(2024, 1, 1), filename="apple.md"),
            FakePage("Mango", date=datetime(2024, 1, 1), filename="mango.md"),
        ]
    )
    # Descending: reverse alphabetical
    sorted_desc = pages.sorted(reverse=True)
    assert [p.title for p in sorted_desc] == ["Zebra", "Mango", "Apple"]

    # Ascending: alphabetical
    sorted_asc = pages.sorted(reverse=False)
    assert [p.title for p in sorted_asc] == ["Apple", "Mango", "Zebra"]


def test_sorting_date_takes_priority():
    """Test that date is primary sort key."""
    pages = PageCollection(
        [
            FakePage("Old Numbered", date=datetime(2024, 1, 1), filename="01-old.md"),
            FakePage("New Unnumbered", date=datetime(2024, 1, 3), filename="new.md"),
            FakePage("Mid", date=datetime(2024, 1, 2), filename="02-mid.md"),
        ]
    )
    # Descending: newest first
    sorted_desc = pages.sorted(reverse=True)
    assert [p.title for p in sorted_desc] == ["New Unnumbered", "Mid", "Old Numbered"]


def test_sorting_with_dated_filenames():
    """Test sorting with dated filenames like 2024-01-15-post.md."""
    pages = PageCollection(
        [
            FakePage("Post C", date=datetime(2024, 1, 15), filename="2024-01-15-03-post-c.md"),
            FakePage("Post A", date=datetime(2024, 1, 15), filename="2024-01-15-01-post-a.md"),
            FakePage("Post B", date=datetime(2024, 1, 15), filename="2024-01-15-02-post-b.md"),
        ]
    )
    # Same date, sort by number after date prefix
    sorted_desc = pages.sorted(reverse=True)
    assert [p.title for p in sorted_desc] == ["Post C", "Post B", "Post A"]

    sorted_asc = pages.sorted(reverse=False)
    assert [p.title for p in sorted_asc] == ["Post A", "Post B", "Post C"]


def test_tag_collection_access():
    p1 = FakePage("T1")
    tags = TagCollection({"python": [p1]})
    assert tags["python"][0] is p1
    assert list(tags) == ["python"]
    assert list(tags.keys()) == ["python"]
    assert list(tags.values())[0][0] is p1
    assert list(tags.items())[0][0] == "python"
    assert tags.get("missing") is None
