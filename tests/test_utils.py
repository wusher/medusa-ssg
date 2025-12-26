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

    # fallback deletion path when rmtree is ineffective
    nested = tmp_path / "stubborn"
    nested.mkdir()
    subdir = nested / "inner"
    subdir.mkdir()
    (subdir / "file.txt").write_text("data", encoding="utf-8")
    original_rmtree = utils.shutil.rmtree

    def fake_rmtree(path, ignore_errors=False):
        return None  # does nothing so fallback is used

    utils.shutil.rmtree = fake_rmtree
    try:
        utils.ensure_clean_dir(nested)
    finally:
        utils.shutil.rmtree = original_rmtree
    assert nested.exists() and list(nested.iterdir()) == []

    missing = tmp_path / "missing-dir"
    utils.ensure_clean_dir(missing)
    assert missing.exists()


def test_path_helpers_and_tags_index(tmp_path):
    path = Path("site/_partials/header.html.jinja")
    assert utils.is_internal_path(path)
    assert utils.is_template(Path("index.html.jinja"))
    assert utils.is_markdown(Path("page.md"))

    # HTML file detection
    assert utils.is_html(Path("page.html"))
    assert utils.is_html(Path("404.html"))
    assert not utils.is_html(Path("page.html.jinja"))  # template, not plain HTML
    assert not utils.is_html(Path("page.md"))
    assert not utils.is_html(Path("page.jinja"))

    class Page:
        def __init__(self, tags):
            self.tags = tags

    pages = [Page(["python", "web"]), Page(["python"])]
    tags = utils.build_tags_index(pages)
    assert set(tags["python"]) == set(pages)


def test_extract_number_from_name():
    # Simple number prefix
    assert utils.extract_number_from_name("01-intro") == 1
    assert utils.extract_number_from_name("2-getting-started") == 2
    assert utils.extract_number_from_name("10-conclusion") == 10

    # No number prefix
    assert utils.extract_number_from_name("intro") is None
    assert utils.extract_number_from_name("about-us") is None

    # Date prefix without number after
    assert utils.extract_number_from_name("2024-01-15-my-post") is None

    # Date prefix with number after
    assert utils.extract_number_from_name("2024-01-15-01-first-section") == 1
    assert utils.extract_number_from_name("2024-01-15-5-middle-section") == 5

    # Layout suffix handling
    assert utils.extract_number_from_name("01-intro[hero]") == 1
    assert utils.extract_number_from_name("2024-01-15-02-post[blog]") == 2


def test_strip_number_prefix():
    # Simple number prefix
    assert utils.strip_number_prefix("01-intro") == "intro"
    assert utils.strip_number_prefix("2-getting-started") == "getting-started"

    # No prefix
    assert utils.strip_number_prefix("intro") == "intro"
    assert utils.strip_number_prefix("about-us") == "about-us"

    # Date prefix only
    assert utils.strip_number_prefix("2024-01-15-my-post") == "my-post"

    # Date prefix with number
    assert utils.strip_number_prefix("2024-01-15-01-first-section") == "first-section"

    # Layout suffix handling
    assert utils.strip_number_prefix("01-intro[hero]") == "intro"
    assert utils.strip_number_prefix("2024-01-15-02-post[blog]") == "post"


def test_join_and_absolutize_urls():
    assert (
        utils.join_root_url("https://example.com", "/posts/")
        == "https://example.com/posts/"
    )
    assert (
        utils.join_root_url("https://example.com/blog/", "posts/")
        == "https://example.com/blog/posts/"
    )
    assert utils.join_root_url("", "/posts/") == "/posts/"

    html = '<a href="/about/"></a><img src="https://cdn.com/x.png"><a href="#frag"></a>'
    rewritten = utils.absolutize_html_urls(html, "https://example.com")
    assert 'href="https://example.com/about/"' in rewritten
    assert "cdn.com" in rewritten
    assert "#frag" in rewritten
    assert utils.absolutize_html_urls(html, "") == html
