from datetime import datetime, timezone

from medusa.collections import PageCollection
from medusa.content import Heading, Page
from medusa.templates import TemplateEngine, render_toc


def test_template_engine_renders_with_layout(tmp_path):
    site = tmp_path / "site"
    (site / "_layouts").mkdir(parents=True)
    (site / "_partials").mkdir()
    (site / "_layouts" / "default.html.jinja").write_text(
        "<title>{{ current_page.title }}</title>{{ page_content }}{{ url_for('assets/js/app.js') }}",
        encoding="utf-8",
    )
    data = {"title": "My Site", "url": "https://example.com"}
    engine = TemplateEngine(site, data)

    page = Page(
        title="Hello",
        body="Hi",
        content="<p>Hi</p>",
        description="Hi",
        excerpt="",
        url="/hello/",
        slug="hello",
        date=datetime.now(timezone.utc),
        tags=[],
        draft=False,
        layout="default",
        group="",
        path=site / "index.md",
        folder="",
        filename="index.md",
        source_type="markdown",
    )

    engine.update_collections(PageCollection([page]), {"python": [page]})
    rendered = engine.render_page(page)
    assert "<p>Hi</p>" in rendered
    assert "https://example.com/assets/js/app.js" in rendered


def test_url_for_without_site_url(tmp_path):
    engine = TemplateEngine(tmp_path, {})
    assert engine._url_for("assets/app.js") == "/assets/app.js"
    assert engine._url_for("http://cdn.com/lib.js") == "http://cdn.com/lib.js"
    assert engine._url_for("/assets/css/main.css") == "/assets/css/main.css"


def test_url_for_prefers_root_url(tmp_path):
    engine = TemplateEngine(
        tmp_path, {"url": "https://site.com"}, root_url="https://root.com"
    )
    assert engine._url_for("/assets/app.js") == "https://root.com/assets/app.js"
    assert engine._url_for("posts/") == "https://root.com/posts/"


def test_render_body_jinja_and_layout_fallback(tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    engine = TemplateEngine(site, {})
    page = Page(
        title="Inline",
        body="Hi",
        content="{{ current_page.title }}",
        description="",
        excerpt="",
        url="/inline/",
        slug="inline",
        date=datetime.now(timezone.utc),
        tags=[],
        draft=False,
        layout="missing-layout",
        group="",
        path=site / "inline.html.jinja",
        folder="",
        filename="inline.html.jinja",
        source_type="jinja",
    )
    engine.update_collections(PageCollection([page]), {})
    rendered = engine.render_page(page)
    assert "Inline" in rendered


def test_missing_partial_falls_back(tmp_path, capsys):
    site = tmp_path / "site"
    (site / "_layouts").mkdir(parents=True)
    (site / "_layouts" / "default.html.jinja").write_text(
        "{% include 'missing.html.jinja' %}{{ page_content }}", encoding="utf-8"
    )
    engine = TemplateEngine(site, {})
    page = Page(
        title="T",
        body="b",
        content="<p>body</p>",
        description="",
        excerpt="",
        url="/",
        slug="",
        date=datetime.now(timezone.utc),
        tags=[],
        draft=False,
        layout="default",
        group="",
        path=site / "index.md",
        folder="",
        filename="index.md",
        source_type="markdown",
    )
    engine.update_collections([page], {})
    out = engine.render_page(page)
    assert "body" in out
    assert "missing.html.jinja" in capsys.readouterr().out


def test_asset_path_helpers(tmp_path):
    """Test js_path, css_path, img_path, and font_path helpers."""
    site = tmp_path / "site"
    site.mkdir()

    # Create assets directory structure
    assets = tmp_path / "assets"
    (assets / "js").mkdir(parents=True)
    (assets / "css").mkdir()
    (assets / "images").mkdir()
    (assets / "fonts").mkdir()

    # Create some image files
    (assets / "images" / "logo.png").write_text("png")
    (assets / "images" / "photo.jpg").write_text("jpg")
    (assets / "images" / "icon.gif").write_text("gif")

    # Create some font files
    (assets / "fonts" / "inter.woff2").write_text("woff2")
    (assets / "fonts" / "roboto.ttf").write_text("ttf")

    engine = TemplateEngine(site, {})

    # js_path
    assert engine._js_path("app") == "/assets/js/app.js"
    assert engine._js_path("vendor/jquery") == "/assets/js/vendor/jquery.js"

    # css_path
    assert engine._css_path("main") == "/assets/css/main.css"
    assert engine._css_path("themes/dark") == "/assets/css/themes/dark.css"

    # img_path - finds existing files with correct extension
    assert engine._img_path("logo") == "/assets/images/logo.png"
    assert engine._img_path("photo") == "/assets/images/photo.jpg"
    assert engine._img_path("icon") == "/assets/images/icon.gif"

    # img_path - falls back to .png for missing files
    assert engine._img_path("missing") == "/assets/images/missing.png"

    # font_path - finds existing files with correct extension
    assert engine._font_path("inter") == "/assets/fonts/inter.woff2"
    assert engine._font_path("roboto") == "/assets/fonts/roboto.ttf"

    # font_path - falls back to .woff2 for missing files
    assert engine._font_path("missing") == "/assets/fonts/missing.woff2"


def test_asset_path_helpers_with_root_url(tmp_path):
    """Test asset helpers respect root_url."""
    site = tmp_path / "site"
    site.mkdir()
    (tmp_path / "assets" / "images").mkdir(parents=True)
    (tmp_path / "assets" / "fonts").mkdir(parents=True)
    (tmp_path / "assets" / "images" / "hero.jpeg").write_text("jpeg")
    (tmp_path / "assets" / "fonts" / "custom.woff").write_text("woff")

    engine = TemplateEngine(site, {}, root_url="https://cdn.example.com")

    assert engine._js_path("app") == "https://cdn.example.com/assets/js/app.js"
    assert engine._css_path("main") == "https://cdn.example.com/assets/css/main.css"
    assert engine._img_path("hero") == "https://cdn.example.com/assets/images/hero.jpeg"
    assert (
        engine._font_path("custom")
        == "https://cdn.example.com/assets/fonts/custom.woff"
    )


def test_asset_path_helpers_with_extension_already_present(tmp_path):
    """Test asset helpers don't double-append extensions."""
    site = tmp_path / "site"
    site.mkdir()
    (tmp_path / "assets" / "images").mkdir(parents=True)
    (tmp_path / "assets" / "fonts").mkdir(parents=True)

    engine = TemplateEngine(site, {})

    # js_path with .js extension
    assert engine._js_path("app.js") == "/assets/js/app.js"
    assert engine._js_path("vendor/lib.js") == "/assets/js/vendor/lib.js"

    # css_path with .css extension
    assert engine._css_path("main.css") == "/assets/css/main.css"
    assert engine._css_path("themes/dark.css") == "/assets/css/themes/dark.css"

    # img_path with various image extensions
    assert engine._img_path("logo.png") == "/assets/images/logo.png"
    assert engine._img_path("photo.jpg") == "/assets/images/photo.jpg"
    assert engine._img_path("icon.svg") == "/assets/images/icon.svg"
    assert engine._img_path("banner.webp") == "/assets/images/banner.webp"

    # font_path with various font extensions
    assert engine._font_path("inter.woff2") == "/assets/fonts/inter.woff2"
    assert engine._font_path("roboto.ttf") == "/assets/fonts/roboto.ttf"
    assert engine._font_path("custom.eot") == "/assets/fonts/custom.eot"


def _make_page_with_toc(tmp_path, toc: list[Heading]) -> Page:
    """Helper to create a Page with a specific TOC."""
    site = tmp_path / "site"
    site.mkdir(exist_ok=True)
    return Page(
        title="Test",
        body="body",
        content="<p>content</p>",
        description="desc",
        excerpt="",
        url="/test/",
        slug="test",
        date=datetime.now(timezone.utc),
        tags=[],
        draft=False,
        layout="default",
        group="",
        path=site / "test.md",
        folder="",
        filename="test.md",
        source_type="markdown",
        toc=toc,
    )


def test_render_toc_empty_for_no_headings(tmp_path):
    """Test render_toc returns empty string for pages without headings."""
    page = _make_page_with_toc(tmp_path, [])
    result = render_toc(page)
    assert result == ""


def test_render_toc_single_heading(tmp_path):
    """Test render_toc with a single heading."""
    page = _make_page_with_toc(
        tmp_path,
        [
            Heading(id="intro", text="Introduction", level=1),
        ],
    )
    result = render_toc(page)
    assert result == '<ul><li><a href="#intro">Introduction</a></li></ul>'


def test_render_toc_flat_headings(tmp_path):
    """Test render_toc with multiple same-level headings."""
    page = _make_page_with_toc(
        tmp_path,
        [
            Heading(id="one", text="One", level=2),
            Heading(id="two", text="Two", level=2),
            Heading(id="three", text="Three", level=2),
        ],
    )
    result = render_toc(page)
    expected = (
        "<ul>"
        '<li><a href="#one">One</a></li>'
        '<li><a href="#two">Two</a></li>'
        '<li><a href="#three">Three</a></li>'
        "</ul>"
    )
    assert result == expected


def test_render_toc_nested_headings(tmp_path):
    """Test render_toc with nested heading levels."""
    page = _make_page_with_toc(
        tmp_path,
        [
            Heading(id="intro", text="Introduction", level=1),
            Heading(id="getting-started", text="Getting Started", level=2),
            Heading(id="prereq", text="Prerequisites", level=3),
            Heading(id="install", text="Installation", level=3),
            Heading(id="advanced", text="Advanced", level=2),
        ],
    )
    result = render_toc(page)
    expected = (
        "<ul>"
        '<li><a href="#intro">Introduction</a>'
        "<ul>"
        '<li><a href="#getting-started">Getting Started</a>'
        "<ul>"
        '<li><a href="#prereq">Prerequisites</a></li>'
        '<li><a href="#install">Installation</a></li>'
        "</ul>"
        "</li>"
        '<li><a href="#advanced">Advanced</a></li>'
        "</ul>"
        "</li>"
        "</ul>"
    )
    assert result == expected


def test_render_toc_escapes_html(tmp_path):
    """Test that render_toc escapes HTML in heading text and IDs."""
    page = _make_page_with_toc(
        tmp_path,
        [
            Heading(id="test-id", text="<script>alert('xss')</script>", level=1),
        ],
    )
    result = render_toc(page)
    assert "<script>" not in result
    assert "&lt;script&gt;" in result


def test_render_toc_available_in_template(tmp_path):
    """Test that render_toc is available as a template global."""
    site = tmp_path / "site"
    (site / "_layouts").mkdir(parents=True)
    (site / "_layouts" / "default.html.jinja").write_text(
        "{{ render_toc(current_page) }}",
        encoding="utf-8",
    )
    engine = TemplateEngine(site, {})

    page = _make_page_with_toc(
        tmp_path,
        [
            Heading(id="hello", text="Hello World", level=1),
        ],
    )
    engine.update_collections(PageCollection([page]), {})
    rendered = engine.render_page(page)
    assert '<a href="#hello">Hello World</a>' in rendered


def test_page_toc_in_template(tmp_path):
    """Test that page.toc is accessible in templates."""
    site = tmp_path / "site"
    (site / "_layouts").mkdir(parents=True)
    (site / "_layouts" / "default.html.jinja").write_text(
        """{% if current_page.toc %}
<nav>
{% for heading in current_page.toc %}
<a href="#{{ heading.id }}">{{ heading.text }} (h{{ heading.level }})</a>
{% endfor %}
</nav>
{% endif %}""",
        encoding="utf-8",
    )
    engine = TemplateEngine(site, {})

    page = _make_page_with_toc(
        tmp_path,
        [
            Heading(id="intro", text="Introduction", level=1),
            Heading(id="details", text="Details", level=2),
        ],
    )
    engine.update_collections(PageCollection([page]), {})
    rendered = engine.render_page(page)

    assert '<a href="#intro">Introduction (h1)</a>' in rendered
    assert '<a href="#details">Details (h2)</a>' in rendered


def test_render_toc_from_headings_empty():
    """Test _render_toc_from_headings with empty list."""
    from medusa.templates import _render_toc_from_headings

    result = _render_toc_from_headings([])
    assert result == ""


def test_render_toc_skip_levels(tmp_path):
    """Test render_toc when skipping heading levels (e.g., h1 -> h3)."""
    page = _make_page_with_toc(
        tmp_path,
        [
            Heading(id="intro", text="Introduction", level=1),
            Heading(id="deep", text="Deep Nested", level=3),  # Skip level 2
            Heading(id="back", text="Back Up", level=2),
        ],
    )
    result = render_toc(page)
    # Should still generate valid nested structure
    assert '<a href="#intro">Introduction</a>' in result
    assert '<a href="#deep">Deep Nested</a>' in result
    assert '<a href="#back">Back Up</a>' in result
    assert "<ul>" in result


def test_pygments_css_returns_styles():
    """Test _pygments_css returns CSS styles when Pygments is available."""
    from medusa.templates import TemplateEngine

    result = TemplateEngine._pygments_css()
    # Should return CSS styles containing .highlight class
    assert isinstance(result, str)
    assert ".highlight" in result or result != ""  # Either has content or is non-empty


def test_pygments_css_import_error():
    """Test _pygments_css returns empty string when Pygments import fails."""
    import sys
    from medusa.templates import TemplateEngine

    # Save all pygments-related modules
    saved_modules = {}
    to_remove = [k for k in sys.modules if k.startswith("pygments")]
    for key in to_remove:
        saved_modules[key] = sys.modules.pop(key)

    # Create a module that raises ImportError on attribute access
    class BrokenModule:
        def __getattr__(self, name):
            raise ImportError(f"mocked ImportError for {name}")

    # Insert the broken module
    sys.modules["pygments"] = BrokenModule()
    sys.modules["pygments.formatters"] = BrokenModule()

    try:
        # Call the actual method - it should handle ImportError gracefully
        result = TemplateEngine._pygments_css()
        assert result == ""
    finally:
        # Clean up broken modules
        for key in ["pygments", "pygments.formatters"]:
            if key in sys.modules:
                del sys.modules[key]
        # Restore original modules
        sys.modules.update(saved_modules)
