from datetime import datetime
from pathlib import Path

from medusa.content import (
    ContentProcessor,
    _extract_excerpt,
    _generate_heading_id,
    _rewrite_image_path,
)


def create_site(tmp_path: Path) -> Path:
    site = tmp_path / "site"
    (site / "_layouts").mkdir(parents=True)
    (site / "_partials").mkdir()
    (site / "posts").mkdir()
    (site / "pages").mkdir()
    (site / "_hidden").mkdir()
    (site / "_partials" / "header.html.jinja").write_text("header", encoding="utf-8")
    (site / "_layouts" / "default.html.jinja").write_text(
        "{{ page_content }}", encoding="utf-8"
    )

    (site / "index.md").write_text(
        "# Home Page\n\nWelcome to the #web frontend.\n\n![Logo](logo.png)",
        encoding="utf-8",
    )
    (site / "pages" / "about.md").write_text("# About Us", encoding="utf-8")
    (site / "pages" / "index.md").write_text("# Pages Index", encoding="utf-8")
    (site / "posts" / "2024-01-15-my-post.md").write_text(
        "# Post Title\n\nBody text #python", encoding="utf-8"
    )
    (site / "posts" / "_draft.md").write_text("# Draft", encoding="utf-8")
    (site / "contact[hero].html.jinja").write_text(
        "<h1>{{ data.title }}</h1>", encoding="utf-8"
    )
    (site / "raw.html.jinja").write_text('<img src="inline.png">', encoding="utf-8")
    (site / "_hidden" / "secret.md").write_text("# Secret", encoding="utf-8")
    (site / "notes.txt").write_text("ignore", encoding="utf-8")
    (site / "rich.md").write_text(
        '# Rich\n\n<div class="hero"><span>HTML stays</span></div>\n', encoding="utf-8"
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
    assert 'img src="/assets/images/logo.png"' in page.content
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
    assert (
        _rewrite_image_path("icons/logo.png", "posts")
        == "/assets/images/posts/icons/logo.png"
    )


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
    (site / "_layouts" / "posts" / "happy.html.jinja").write_text(
        "ph", encoding="utf-8"
    )

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


def test_html_file_processing(tmp_path):
    """Test that plain HTML files are processed as pages."""
    site = tmp_path / "site"
    (site / "_layouts").mkdir(parents=True)
    (site / "_layouts" / "default.html.jinja").write_text(
        "{{ page_content }}", encoding="utf-8"
    )

    # Plain HTML file should be processed
    (site / "about.html").write_text(
        "<h1>About Us</h1><p>Welcome to our site.</p>", encoding="utf-8"
    )
    (site / "404.html").write_text(
        "<h1>Not Found</h1><p>Page not found.</p>", encoding="utf-8"
    )

    pages = ContentProcessor(site).load()
    urls = {p.url for p in pages}

    assert "/about/" in urls
    assert "/404/" in urls

    about = next(p for p in pages if p.url == "/about/")
    assert about.source_type == "html"
    # Title comes from filename for HTML files (no markdown # heading parsing)
    assert about.title == "About"
    assert "<h1>About Us</h1>" in about.content

    not_found = next(p for p in pages if p.url == "/404/")
    assert not_found.source_type == "html"


def test_html_file_in_subfolder(tmp_path):
    """Test that HTML files in subfolders are processed correctly."""
    site = tmp_path / "site"
    (site / "_layouts").mkdir(parents=True)
    (site / "_layouts" / "default.html.jinja").write_text(
        "{{ page_content }}", encoding="utf-8"
    )
    (site / "pages").mkdir()

    (site / "pages" / "contact.html").write_text(
        "<h1>Contact</h1><p>Get in touch.</p>", encoding="utf-8"
    )

    pages = ContentProcessor(site).load()
    urls = {p.url for p in pages}

    assert "/pages/contact/" in urls
    page = next(p for p in pages if p.url == "/pages/contact/")
    assert page.source_type == "html"
    assert page.group == "pages"


def test_code_files_not_processed(tmp_path):
    """Test that code files (.py, .js, etc.) are no longer processed."""
    site = tmp_path / "site"
    (site / "_layouts").mkdir(parents=True)
    (site / "_layouts" / "default.html.jinja").write_text(
        "{{ page_content }}", encoding="utf-8"
    )
    (site / "snippets").mkdir()

    # Code files should NOT be rendered
    (site / "snippets" / "example.py").write_text(
        '# Example script\nprint("Hello")', encoding="utf-8"
    )
    (site / "script.js").write_text('console.log("hi")', encoding="utf-8")
    # But markdown should work
    (site / "index.md").write_text("# Home", encoding="utf-8")

    pages = ContentProcessor(site).load()
    urls = {p.url for p in pages}

    assert "/" in urls  # markdown works
    assert "/snippets/example/" not in urls  # code file ignored
    assert "/script/" not in urls  # code file in root ignored


def test_frontmatter_extraction(tmp_path):
    """Test YAML frontmatter is parsed and available as dict."""
    site = tmp_path / "site"
    (site / "_layouts").mkdir(parents=True)
    (site / "_layouts" / "default.html.jinja").write_text(
        "{{ page_content }}", encoding="utf-8"
    )
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
    (site / "_layouts" / "default.html.jinja").write_text(
        "{{ page_content }}", encoding="utf-8"
    )

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


def test_generate_heading_id():
    """Test heading ID generation from text."""
    assert _generate_heading_id("Hello World") == "hello-world"
    assert _generate_heading_id("  Spaces  Around  ") == "spaces-around"
    assert _generate_heading_id("Special!@#$%Chars") == "specialchars"
    assert _generate_heading_id("Multiple---Dashes") == "multiple-dashes"
    assert _generate_heading_id("123 Numbers") == "123-numbers"


def test_toc_extraction_from_markdown(tmp_path):
    """Test that TOC is extracted from markdown headings."""
    site = tmp_path / "site"
    (site / "_layouts").mkdir(parents=True)
    (site / "_layouts" / "default.html.jinja").write_text(
        "{{ page_content }}", encoding="utf-8"
    )

    (site / "article.md").write_text(
        """# Introduction

Some intro text.

## Getting Started

Getting started guide.

### Prerequisites

Things you need.

## Advanced Topics

Advanced content.

### Configuration

Config details.

### Troubleshooting

Fixing issues.
""",
        encoding="utf-8",
    )

    pages = ContentProcessor(site).load()
    page = next(p for p in pages if "article" in p.url)

    # Should have 6 headings
    assert len(page.toc) == 6

    # Check heading properties
    assert page.toc[0].text == "Introduction"
    assert page.toc[0].level == 1
    assert page.toc[0].id == "introduction"

    assert page.toc[1].text == "Getting Started"
    assert page.toc[1].level == 2
    assert page.toc[1].id == "getting-started"

    assert page.toc[2].text == "Prerequisites"
    assert page.toc[2].level == 3
    assert page.toc[2].id == "prerequisites"

    # Verify headings have IDs in the rendered content
    assert 'id="introduction"' in page.content
    assert 'id="getting-started"' in page.content
    assert 'id="prerequisites"' in page.content


def test_toc_handles_duplicate_headings(tmp_path):
    """Test that duplicate headings get unique IDs."""
    site = tmp_path / "site"
    (site / "_layouts").mkdir(parents=True)
    (site / "_layouts" / "default.html.jinja").write_text(
        "{{ page_content }}", encoding="utf-8"
    )

    (site / "duplicates.md").write_text(
        """# Overview

## Features

Some features.

## Features

More features.

## Features

Even more features.
""",
        encoding="utf-8",
    )

    pages = ContentProcessor(site).load()
    page = next(p for p in pages if "duplicates" in p.url)

    # Should have 4 headings
    assert len(page.toc) == 4

    # Check that duplicate headings get unique IDs
    assert page.toc[0].id == "overview"
    assert page.toc[1].id == "features"
    assert page.toc[2].id == "features-1"
    assert page.toc[3].id == "features-2"

    # Verify unique IDs in content
    assert 'id="features"' in page.content
    assert 'id="features-1"' in page.content
    assert 'id="features-2"' in page.content


def test_toc_empty_for_no_headings(tmp_path):
    """Test that pages without headings have empty TOC."""
    site = tmp_path / "site"
    (site / "_layouts").mkdir(parents=True)
    (site / "_layouts" / "default.html.jinja").write_text(
        "{{ page_content }}", encoding="utf-8"
    )

    (site / "no-headings.md").write_text(
        "Just some paragraph text.\n\nAnother paragraph.",
        encoding="utf-8",
    )

    pages = ContentProcessor(site).load()
    page = next(p for p in pages if "no-headings" in p.url)

    assert page.toc == []


def test_toc_empty_for_jinja_templates(tmp_path):
    """Test that jinja templates have empty TOC (no markdown parsing)."""
    site = tmp_path / "site"
    (site / "_layouts").mkdir(parents=True)
    (site / "_layouts" / "default.html.jinja").write_text(
        "{{ page_content }}", encoding="utf-8"
    )

    (site / "template.html.jinja").write_text(
        "<h1>Heading One</h1><h2>Heading Two</h2>",
        encoding="utf-8",
    )

    pages = ContentProcessor(site).load()
    page = next(p for p in pages if "template" in p.url)

    # Jinja templates are not parsed for markdown, so no TOC
    assert page.toc == []


def test_extract_excerpt():
    """Test excerpt extraction from markdown text."""
    # Basic case: heading followed by paragraph
    text = "# Title\n\nThis is the first paragraph.\n\nSecond paragraph."
    assert _extract_excerpt(text) == "This is the first paragraph."

    # Multiple headings before first paragraph
    text = "# Title\n\n## Subtitle\n\nActual content here."
    assert _extract_excerpt(text) == "Actual content here."

    # Multiline paragraph gets collapsed
    text = "# Title\n\nFirst line\nof the paragraph\nspans multiple lines."
    assert _extract_excerpt(text) == "First line of the paragraph spans multiple lines."

    # Skip images
    text = "# Title\n\n![alt](image.png)\n\nActual paragraph."
    assert _extract_excerpt(text) == "Actual paragraph."

    # Skip code blocks
    text = "# Title\n\n```python\ncode\n```\n\nActual paragraph."
    assert _extract_excerpt(text) == "Actual paragraph."

    # Empty text
    assert _extract_excerpt("") == ""

    # Only headings
    assert _extract_excerpt("# Title\n\n## Subtitle") == ""


def test_excerpt_from_markdown_page(tmp_path):
    """Test that excerpt is extracted from markdown pages."""
    site = tmp_path / "site"
    (site / "_layouts").mkdir(parents=True)
    (site / "_layouts" / "default.html.jinja").write_text(
        "{{ page_content }}", encoding="utf-8"
    )

    (site / "post.md").write_text(
        """# My Blog Post

This is the introduction paragraph that should become the excerpt.
It spans multiple lines but should be collapsed.

## Section One

More content here.
""",
        encoding="utf-8",
    )

    pages = ContentProcessor(site).load()
    page = next(p for p in pages if "post" in p.url)

    assert (
        page.excerpt
        == "This is the introduction paragraph that should become the excerpt. It spans multiple lines but should be collapsed."
    )


def test_excerpt_empty_for_jinja_templates(tmp_path):
    """Test that jinja templates have empty excerpt."""
    site = tmp_path / "site"
    (site / "_layouts").mkdir(parents=True)
    (site / "_layouts" / "default.html.jinja").write_text(
        "{{ page_content }}", encoding="utf-8"
    )

    (site / "page.html.jinja").write_text(
        "<h1>Title</h1><p>Some content</p>",
        encoding="utf-8",
    )

    pages = ContentProcessor(site).load()
    page = next(p for p in pages if "page" in p.url)

    assert page.excerpt == ""


def test_excerpt_skips_hashtags(tmp_path):
    """Test that hashtags are stripped before extracting excerpt."""
    site = tmp_path / "site"
    (site / "_layouts").mkdir(parents=True)
    (site / "_layouts" / "default.html.jinja").write_text(
        "{{ page_content }}", encoding="utf-8"
    )

    (site / "tagged.md").write_text(
        """# Post with Tags

This post is about #python and #testing.

More content.
""",
        encoding="utf-8",
    )

    pages = ContentProcessor(site).load()
    page = next(p for p in pages if "tagged" in p.url)

    # Hashtags should be stripped
    assert "#python" not in page.excerpt
    assert "This post is about" in page.excerpt


def test_frontmatter_non_dict_yaml(tmp_path):
    """Test that frontmatter with non-dict YAML returns empty dict."""
    from medusa.content import _extract_frontmatter

    # YAML that parses to a list
    text = """---
- item1
- item2
---

# Content
"""
    frontmatter, body = _extract_frontmatter(text)
    assert frontmatter == {}
    assert "# Content" in body


def test_frontmatter_invalid_yaml(tmp_path):
    """Test that invalid YAML frontmatter returns empty dict."""
    from medusa.content import _extract_frontmatter

    # Invalid YAML syntax
    text = """---
key: value
  invalid: indentation
---

# Content
"""
    frontmatter, body = _extract_frontmatter(text)
    assert frontmatter == {}
    assert "# Content" in body


def test_code_block_with_valid_language():
    """Test code block rendering with valid language uses Pygments."""
    from medusa.content import _HighlightRenderer

    renderer = _HighlightRenderer("")
    result = renderer.block_code("print('hello')", info="python")
    # Should have Pygments highlight class
    assert "highlight" in result
    assert "print" in result


def test_code_block_with_invalid_language(tmp_path):
    """Test code block rendering falls back when lexer not found."""
    from medusa.content import _HighlightRenderer

    renderer = _HighlightRenderer("")
    # Use a made-up language that doesn't exist
    result = renderer.block_code("code here", info="nonexistent_language_xyz123")
    # Should fall back to plain code block
    assert "<pre><code" in result
    assert "code here" in result


def test_code_block_without_language_info():
    """Test code block rendering without language specification."""
    from medusa.content import _HighlightRenderer

    renderer = _HighlightRenderer("")
    # No language info - should use plain fallback
    result = renderer.block_code("plain code", info=None)
    assert "<pre><code>" in result
    assert "plain code" in result

    # Empty string language
    result = renderer.block_code("plain code", info="")
    assert "<pre><code>" in result
    assert "plain code" in result
