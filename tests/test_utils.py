from datetime import datetime
from pathlib import Path

from medusa import utils


def test_slugify_and_titleize_strip_date_and_layout():
    assert utils.slugify("2024-01-02-post-title") == "post-title"
    assert utils.slugify("contact[form]") == "contact"
    assert utils.slugify("mixed-case-slug") == "mixed-case-slug"
    assert utils.slugify("!!!") == "index"
    assert utils.titleize("2024-01-02-post-title.md") == "Post Title"
    assert utils.titleize("contact[form].md") == "Contact"
    assert utils.titleize("mixed-case-slug.md") == "Mixed Case Slug"


def test_extract_date_tags_and_strip():
    date = utils.extract_date_from_name("2024-01-15-cool")
    assert date == datetime(2024, 1, 15)
    assert utils.extract_date_from_name("invalid") is None
    assert utils.extract_date_from_name("2024-13-32-post") is None

    text = "Talking about #python and #web/frontend plus #python again."
    assert utils.extract_tags(text) == ["python", "web/frontend"]
    assert utils.strip_hashtags(text).startswith("Talking about python")


def test_first_paragraph_and_wrapping(tmp_path):
    text = "First paragraph.\n\nSecond paragraph that should be ignored."
    assert utils.first_paragraph(text, limit=40) == "First paragraph."
    assert utils.first_paragraph("") == ""
    assert "wrap" in utils.limit_lines("wrap " * 10, width=20)

    target = tmp_path / "build"
    target.mkdir()
    (target / "old.txt").write_text("old", encoding="utf-8")
    utils.ensure_clean_dir(target)
    assert list(target.iterdir()) == []


def test_path_helpers_and_tags_index(tmp_path):
    path = Path("site/_partials/header.html.jinja")
    assert utils.is_internal_path(path)
    assert utils.is_template(Path("index.html.jinja"))
    assert utils.is_markdown(Path("page.md"))

    class Page:
        def __init__(self, tags):
            self.tags = tags

    pages = [Page(["python", "web"]), Page(["python"])]
    tags = utils.build_tags_index(pages)
    assert set(tags["python"]) == set(pages)
