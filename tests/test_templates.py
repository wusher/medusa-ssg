from datetime import datetime, timezone
from pathlib import Path

from medusa.content import Page
from medusa.collections import PageCollection, TagCollection
from medusa.templates import TemplateEngine


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
    engine = TemplateEngine(tmp_path, {"url": "https://site.com"}, root_url="https://root.com")
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
    assert engine._font_path("custom") == "https://cdn.example.com/assets/fonts/custom.woff"
