from datetime import datetime
from pathlib import Path

from medusa.content import ContentProcessor, _rewrite_image_path


def create_site(tmp_path: Path) -> Path:
    site = tmp_path / "site"
    (site / "_layouts").mkdir(parents=True)
    (site / "_partials").mkdir()
    (site / "posts").mkdir()
    (site / "pages").mkdir()
    (site / "_hidden").mkdir()
    (site / "_partials" / "header.html.jinja").write_text("header", encoding="utf-8")
    (site / "_layouts" / "default.html.jinja").write_text("{{ page_content }}", encoding="utf-8")

    (site / "index.md").write_text(
        "# Home Page\n\nWelcome to the #web frontend.\n\n![Logo](logo.png)",
        encoding="utf-8",
    )
    (site / "pages" / "about.md").write_text("# About Us", encoding="utf-8")
    (site / "pages" / "index.md").write_text("# Pages Index", encoding="utf-8")
    (site / "posts" / "2024-01-15-my-post.md").write_text("# Post Title\n\nBody text #python", encoding="utf-8")
    (site / "posts" / "_draft.md").write_text("# Draft", encoding="utf-8")
    (site / "contact[hero].html.jinja").write_text("<h1>{{ data.title }}</h1>", encoding="utf-8")
    (site / "raw.html.jinja").write_text('<img src="inline.png">', encoding="utf-8")
    (site / "_hidden" / "secret.md").write_text("# Secret", encoding="utf-8")
    (site / "notes.txt").write_text("ignore", encoding="utf-8")
    (site / "rich.md").write_text(
        "# Rich\n\n<div class=\"hero\"><span>HTML stays</span></div>\n", encoding="utf-8"
    )
    return site


def test_content_processing_builds_pages(tmp_path):
    site = create_site(tmp_path)
    pages = ContentProcessor(site).load()
    urls = {p.url for p in pages}
    assert "/" in urls
    assert "/pages/about/" in urls
    assert "/posts/my-post/" in urls
    assert all(not p.draft for p in pages)

    page = next(p for p in pages if p.url == "/")
    assert "img src=\"/assets/images/logo.png\"" in page.content
    assert page.tags == ["web"]
    assert page.group == ""
    assert page.layout == "default"
    assert page.description.startswith("Home Page")

    post = next(p for p in pages if p.group == "posts")
    assert post.slug == "my-post"
    assert post.date == datetime(2024, 1, 15)
    assert post.layout == "default"

    contact = next(p for p in pages if p.layout == "hero")
    assert contact.source_type == "jinja"

    raw = next(p for p in pages if p.filename == "raw.html.jinja")
    assert "/assets/images/inline.png" in raw.content

    rich = next(p for p in pages if p.filename == "rich.md")
    assert '<div class="hero"><span>HTML stays</span></div>' in rich.content


def test_include_drafts_and_url_rules(tmp_path):
    site = create_site(tmp_path)
    drafts = ContentProcessor(site).load(include_drafts=True)
    assert any(p.draft for p in drafts)
    draft = next(p for p in drafts if p.draft)
    assert draft.url == "/posts/draft/"

    assert _rewrite_image_path("/static/logo.png", "posts") == "/static/logo.png"
    assert _rewrite_image_path("icons/logo.png", "posts") == "/assets/images/posts/icons/logo.png"


def test_rewrite_inline_images(tmp_path):
    processor = ContentProcessor(tmp_path)
    html = '<p><img src="photo.png"></p>'
    rewritten = processor._rewrite_inline_images(html, "gallery")
    assert "/assets/images/gallery/photo.png" in rewritten


def test_layout_resolution_specificity(tmp_path):
    site = tmp_path / "site"
    (site / "_layouts").mkdir(parents=True)
    (site / "_layouts" / "default.html.jinja").write_text("d", encoding="utf-8")
    (site / "_layouts" / "about.html.jinja").write_text("a", encoding="utf-8")
    (site / "_layouts" / "posts.html.jinja").write_text("p", encoding="utf-8")
    (site / "_layouts" / "posts").mkdir()
    (site / "_layouts" / "posts" / "happy.html.jinja").write_text("ph", encoding="utf-8")

    processor = ContentProcessor(site)

    about_path = site / "about.md"
    about_path.write_text("# About", encoding="utf-8")
    about_page = processor._build_page(about_path, draft=False)
    assert about_page.layout == "about"

    happy_path = site / "posts" / "happy.md"
    happy_path.parent.mkdir(parents=True, exist_ok=True)
    happy_path.write_text("# Happy", encoding="utf-8")
    happy_page = processor._build_page(happy_path, draft=False)
    assert happy_page.layout == "posts/happy"

    other_path = site / "posts" / "other.md"
    other_path.write_text("# Other", encoding="utf-8")
    other_page = processor._build_page(other_path, draft=False)
    assert other_page.layout == "posts"


def test_layout_resolution_missing_layouts(tmp_path):
    site = tmp_path / "site"
    site.mkdir(parents=True)
    processor = ContentProcessor(site)
    path = site / "orphan.md"
    path.write_text("# Orphan", encoding="utf-8")
    page = processor._build_page(path, draft=False)
    assert page.layout == "default"


def test_code_file_in_subfolder_renders(tmp_path):
    """Test that code files in subfolders are rendered with syntax highlighting."""
    site = tmp_path / "site"
    (site / "_layouts").mkdir(parents=True)
    (site / "_layouts" / "default.html.jinja").write_text("{{ page_content }}", encoding="utf-8")
    (site / "snippets").mkdir()

    # Code file in subfolder should be rendered
    (site / "snippets" / "example.py").write_text(
        '# Example script\nprint("Hello, World!")', encoding="utf-8"
    )

    pages = ContentProcessor(site).load()
    urls = {p.url for p in pages}

    assert "/snippets/example/" in urls
    code_page = next(p for p in pages if p.url == "/snippets/example/")
    assert code_page.source_type == "code"
    assert code_page.title == "Example"
    assert "Hello, World!" in code_page.content
    # Should have Pygments highlight class or code tag
    assert "highlight" in code_page.content or "<code" in code_page.content


def test_code_file_in_root_ignored(tmp_path):
    """Test that code files in root site/ directory are ignored."""
    site = tmp_path / "site"
    (site / "_layouts").mkdir(parents=True)
    (site / "_layouts" / "default.html.jinja").write_text("{{ page_content }}", encoding="utf-8")

    # Code file in root should NOT be rendered
    (site / "script.py").write_text('print("Ignored")', encoding="utf-8")
    # But markdown in root should work
    (site / "index.md").write_text("# Home", encoding="utf-8")

    pages = ContentProcessor(site).load()
    urls = {p.url for p in pages}

    assert "/" in urls  # markdown works
    assert "/script/" not in urls  # code file ignored


def test_code_file_date_extraction(tmp_path):
    """Test date extraction from code file names."""
    site = tmp_path / "site"
    (site / "_layouts").mkdir(parents=True)
    (site / "_layouts" / "default.html.jinja").write_text("{{ page_content }}", encoding="utf-8")
    (site / "tutorials").mkdir()

    (site / "tutorials" / "2024-06-15-my-script.py").write_text("x = 1", encoding="utf-8")

    pages = ContentProcessor(site).load()
    page = next(p for p in pages if "my-script" in p.url)

    assert page.date == datetime(2024, 6, 15)
    assert page.slug == "my-script"
    assert page.title == "My Script"
    assert page.group == "tutorials"


def test_code_file_description_extraction(tmp_path):
    """Test description extraction from code comments."""
    site = tmp_path / "site"
    (site / "_layouts").mkdir(parents=True)
    (site / "_layouts" / "default.html.jinja").write_text("{{ page_content }}", encoding="utf-8")
    (site / "code").mkdir()

    # Python comment
    (site / "code" / "py-comment.py").write_text("# A helpful script\nx = 1", encoding="utf-8")
    # Python docstring
    (site / "code" / "py-docstring.py").write_text('"""A useful module."""\nx = 1', encoding="utf-8")
    # JS comment
    (site / "code" / "js-comment.js").write_text("// JavaScript helper\nconst x = 1;", encoding="utf-8")

    pages = ContentProcessor(site).load()

    py_comment = next(p for p in pages if "py-comment" in p.url)
    assert py_comment.description == "A helpful script"

    py_docstring = next(p for p in pages if "py-docstring" in p.url)
    assert py_docstring.description == "A useful module."

    js_comment = next(p for p in pages if "js-comment" in p.url)
    assert js_comment.description == "JavaScript helper"


def test_frontmatter_extraction(tmp_path):
    """Test YAML frontmatter is parsed and available as dict."""
    site = tmp_path / "site"
    (site / "_layouts").mkdir(parents=True)
    (site / "_layouts" / "default.html.jinja").write_text("{{ page_content }}", encoding="utf-8")
    (site / "posts").mkdir()

    (site / "posts" / "with-frontmatter.md").write_text(
        """---
author: John Doe
category: tutorials
featured: true
custom_list:
  - one
  - two
---

# Markdown Title

Body content here.
""",
        encoding="utf-8",
    )

    pages = ContentProcessor(site).load()
    page = next(p for p in pages if "with-frontmatter" in p.url)

    # Frontmatter is just data - doesn't affect page properties
    assert page.title == "Markdown Title"  # From heading, not frontmatter
    assert page.layout == "default"  # Auto-detected, not from frontmatter

    # Frontmatter dict has all fields
    assert page.frontmatter["author"] == "John Doe"
    assert page.frontmatter["category"] == "tutorials"
    assert page.frontmatter["featured"] is True
    assert page.frontmatter["custom_list"] == ["one", "two"]


def test_frontmatter_empty_or_missing(tmp_path):
    """Test handling of empty or missing frontmatter."""
    site = tmp_path / "site"
    (site / "_layouts").mkdir(parents=True)
    (site / "_layouts" / "default.html.jinja").write_text("{{ page_content }}", encoding="utf-8")

    # Empty frontmatter
    (site / "empty-fm.md").write_text(
        """---
---

# Title From Heading
""",
        encoding="utf-8",
    )

    # No frontmatter
    (site / "no-fm.md").write_text("# Regular Markdown\n\nContent", encoding="utf-8")

    pages = ContentProcessor(site).load()

    empty = next(p for p in pages if "empty-fm" in p.url)
    assert empty.title == "Title From Heading"
    assert empty.frontmatter == {}

    no_fm = next(p for p in pages if "no-fm" in p.url)
    assert no_fm.title == "Regular Markdown"
    assert no_fm.frontmatter == {}
