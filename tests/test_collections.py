from datetime import datetime

from medusa.collections import PageCollection, TagCollection


class FakePage:
    def __init__(self, title, group="", date=None, tags=None, draft=False):
        self.title = title
        self.group = group
        self.date = date or datetime(2024, 1, 1)
        self.tags = tags or []
        self.draft = draft


def test_page_collection_filters_and_latest():
    pages = PageCollection(
        [
            FakePage("A", group="posts", date=datetime(2024, 1, 2)),
            FakePage("B", group="posts", date=datetime(2024, 1, 3), draft=True),
            FakePage("C", group="docs", date=datetime(2024, 1, 1), tags=["python"]),
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


def test_tag_collection_access():
    p1 = FakePage("T1")
    tags = TagCollection({"python": [p1]})
    assert tags["python"][0] is p1
    assert list(tags) == ["python"]
    assert list(tags.keys()) == ["python"]
    assert list(tags.values())[0][0] is p1
    assert list(tags.items())[0][0] == "python"
    assert tags.get("missing") is None
