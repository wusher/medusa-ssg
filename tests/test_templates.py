from datetime import datetime, timezone
from pathlib import Path

from medusa.content import Page
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

    engine.update_collections([page], {"python": [page]})
    rendered = engine.render_page(page)
    assert "<p>Hi</p>" in rendered
    assert "https://example.com/assets/js/app.js" in rendered


def test_url_for_without_site_url(tmp_path):
    engine = TemplateEngine(tmp_path, {})
    assert engine._url_for("assets/app.js") == "/assets/app.js"
    assert engine._url_for("http://cdn.com/lib.js") == "http://cdn.com/lib.js"


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
    engine.update_collections([page], {})
    rendered = engine.render_page(page)
    assert "Inline" in rendered
