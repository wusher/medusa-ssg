"""Tests for the SOLID refactored modules.

Tests for protocols, extractors, renderers, asset_processors, and asset_resolver modules.
"""

from datetime import datetime
from pathlib import Path

import pytest

from medusa.asset_processors import (
    AssetProcessorRegistry,
    CSSProcessor,
    ImageProcessor,
    JSProcessor,
    StaticAssetProcessor,
    TailwindCSSProcessor,
    create_default_registry,
)
from medusa.asset_resolver import AssetNotFoundError, DefaultAssetPathResolver
from medusa.content import (
    ContentProcessor,
    DefaultPageBuilder,
    FileContentLoader,
    LayoutResolver,
    UrlDeriver,
)
from medusa.extractors import (
    CompositeMetadataExtractor,
    DateExtractor,
    DescriptionExtractor,
    FrontmatterExtractor,
    TagExtractor,
    TitleExtractor,
)
from medusa.renderers import (
    HTMLRenderer,
    JinjaContentRenderer,
    MarkdownRenderer,
    RendererRegistry,
)

# --- Extractor Tests ---


def test_title_extractor():
    """Test TitleExtractor extracts title from heading."""
    extractor = TitleExtractor()
    result = extractor.extract("# My Title\n\nContent", Path("test.md"))
    assert result["title"] == "My Title"


def test_title_extractor_fallback():
    """Test TitleExtractor falls back to filename."""
    extractor = TitleExtractor()
    result = extractor.extract("No heading here", Path("my-test-file.md"))
    assert "My Test File" in result["title"]


def test_tag_extractor():
    """Test TagExtractor extracts hashtags."""
    extractor = TagExtractor()
    result = extractor.extract("Some #tag and #another", Path("test.md"))
    assert "tag" in result["tags"]
    assert "another" in result["tags"]


def test_date_extractor_from_filename(tmp_path):
    """Test DateExtractor extracts date from filename."""
    test_file = tmp_path / "2024-01-15-test.md"
    test_file.write_text("content")
    extractor = DateExtractor()
    result = extractor.extract("", test_file)
    assert result["date"].year == 2024
    assert result["date"].month == 1
    assert result["date"].day == 15


def test_date_extractor_fallback(tmp_path):
    """Test DateExtractor falls back to mtime."""
    test_file = tmp_path / "test.md"
    test_file.write_text("content")
    extractor = DateExtractor()
    result = extractor.extract("", test_file)
    assert isinstance(result["date"], datetime)


def test_description_extractor():
    """Test DescriptionExtractor extracts description and excerpt."""
    extractor = DescriptionExtractor()
    # The first_paragraph function strips the heading
    result = extractor.extract(
        "Some content here.\n\nSecond paragraph.", Path("test.md")
    )
    assert "Some content" in result["description"]
    assert "Some content" in result["excerpt"]


def test_frontmatter_extractor():
    """Test FrontmatterExtractor extracts YAML frontmatter."""
    extractor = FrontmatterExtractor()
    content = "---\ntitle: Test\n---\nContent"
    result = extractor.extract(content, Path("test.md"))
    assert result["frontmatter"]["title"] == "Test"
    assert result["body"] == "Content"


def test_composite_extractor():
    """Test CompositeMetadataExtractor combines extractors."""
    extractor = CompositeMetadataExtractor([TitleExtractor()])
    result = extractor.extract("# Title", Path("test.md"))
    assert result["title"] == "Title"


def test_composite_extractor_add():
    """Test adding extractors to composite."""
    extractor = CompositeMetadataExtractor([])
    extractor.add_extractor(TitleExtractor())
    result = extractor.extract("# Title", Path("test.md"))
    assert result["title"] == "Title"


# --- Renderer Tests ---


def test_markdown_renderer():
    """Test MarkdownRenderer renders markdown to HTML."""
    renderer = MarkdownRenderer()
    assert renderer.can_render(Path("test.md"))
    assert not renderer.can_render(Path("test.html"))
    assert renderer.source_type == "markdown"
    html, headings = renderer.render("# Hello\n\nWorld", "")
    assert "<h1" in html
    assert "Hello" in html


def test_html_renderer():
    """Test HTMLRenderer passes through HTML."""
    renderer = HTMLRenderer()
    assert renderer.can_render(Path("test.html"))
    assert not renderer.can_render(Path("test.md"))
    assert renderer.source_type == "html"
    html, headings = renderer.render("<p>Test</p>", "")
    assert html == "<p>Test</p>"
    assert headings == []


def test_jinja_renderer():
    """Test JinjaContentRenderer identifies Jinja templates."""
    renderer = JinjaContentRenderer()
    assert renderer.can_render(Path("test.html.jinja"))
    assert renderer.can_render(Path("test.jinja"))
    assert not renderer.can_render(Path("test.html"))
    assert renderer.source_type == "jinja"
    content, headings = renderer.render("{{ var }}", "")
    assert content == "{{ var }}"


def test_renderer_registry():
    """Test RendererRegistry finds appropriate renderers."""
    registry = RendererRegistry()
    md_renderer = registry.get_renderer(Path("test.md"))
    assert md_renderer is not None
    assert md_renderer.source_type == "markdown"

    html_renderer = registry.get_renderer(Path("test.html"))
    assert html_renderer is not None
    assert html_renderer.source_type == "html"


def test_renderer_registry_unknown():
    """Test RendererRegistry returns None for unknown types."""
    registry = RendererRegistry()
    assert registry.get_renderer(Path("test.xyz")) is None


# --- Asset Processor Tests ---


def test_image_processor(tmp_path):
    """Test ImageProcessor processes images."""
    processor = ImageProcessor()
    assert processor.can_process(Path("test.png"))
    assert processor.can_process(Path("test.jpg"))
    assert not processor.can_process(Path("test.txt"))
    assert processor.priority == 100

    # Test processing
    source = tmp_path / "source.png"
    dest = tmp_path / "out" / "source.png"

    # Create a simple image
    from PIL import Image

    img = Image.new("RGB", (10, 10), color="red")
    img.save(source)

    processor.process(source, dest)
    assert dest.exists()


def test_image_processor_fallback(tmp_path, monkeypatch):
    """Test ImageProcessor falls back when PIL fails."""
    monkeypatch.setattr("medusa.asset_processors.Image", None)
    processor = ImageProcessor()

    source = tmp_path / "source.txt"
    source.write_text("fake image")
    dest = tmp_path / "out" / "source.txt"

    processor.process(source, dest)
    assert dest.exists()


def test_css_processor(tmp_path):
    """Test CSSProcessor copies CSS files."""
    processor = CSSProcessor()
    assert processor.can_process(Path("style.css"))
    assert not processor.can_process(Path("main.css"))  # Tailwind
    assert processor.priority == 90

    source = tmp_path / "style.css"
    source.write_text("body {}")
    dest = tmp_path / "out" / "style.css"

    processor.process(source, dest)
    assert dest.read_text() == "body {}"


def test_js_processor_with_jsmin(tmp_path):
    """Test JSProcessor minifies with rjsmin."""
    processor = JSProcessor(tmp_path)
    assert processor.can_process(Path("app.js"))
    assert processor.priority == 80

    source = tmp_path / "app.js"
    source.write_text("function test() { return 1; }")
    dest = tmp_path / "out" / "app.js"

    processor.process(source, dest)
    assert dest.exists()


def test_js_processor_fallback(tmp_path, monkeypatch):
    """Test JSProcessor falls back to copy when minifiers unavailable."""
    monkeypatch.setattr("medusa.asset_processors.jsmin", None)
    monkeypatch.setattr("shutil.which", lambda x: None)

    processor = JSProcessor(tmp_path)
    source = tmp_path / "app.js"
    source.write_text("function test() { return 1; }")
    dest = tmp_path / "out" / "app.js"

    processor.process(source, dest)
    assert dest.exists()
    assert "function test" in dest.read_text()


def test_static_asset_processor(tmp_path):
    """Test StaticAssetProcessor copies any file."""
    processor = StaticAssetProcessor()
    assert processor.can_process(Path("any.file"))
    assert processor.priority == 0

    source = tmp_path / "file.txt"
    source.write_text("content")
    dest = tmp_path / "out" / "file.txt"

    processor.process(source, dest)
    assert dest.read_text() == "content"


def test_tailwind_processor(tmp_path, monkeypatch):
    """Test TailwindCSSProcessor processes main.css."""
    processor = TailwindCSSProcessor(tmp_path, tmp_path / "out")
    assert processor.can_process(Path("main.css"))
    assert not processor.can_process(Path("other.css"))
    assert processor.priority == 95


def test_tailwind_processor_missing(tmp_path, monkeypatch, capsys):
    """Test TailwindCSSProcessor falls back when CLI missing."""
    monkeypatch.setattr("shutil.which", lambda x: None)

    processor = TailwindCSSProcessor(tmp_path, tmp_path / "out")
    source = tmp_path / "main.css"
    source.write_text("@tailwind base;")
    dest = tmp_path / "out" / "main.css"

    processor.process(source, dest)
    assert dest.exists()
    captured = capsys.readouterr()
    assert "Tailwind CSS CLI not found" in captured.out


def test_asset_processor_registry():
    """Test AssetProcessorRegistry manages processors."""
    registry = AssetProcessorRegistry()
    registry.register(ImageProcessor())
    registry.register(CSSProcessor())

    assert registry.get_processor(Path("test.png")) is not None
    assert registry.get_processor(Path("test.css")) is not None


def test_create_default_registry(tmp_path):
    """Test create_default_registry creates configured registry."""
    registry = create_default_registry(tmp_path, tmp_path / "out")
    assert registry.get_processor(Path("test.png")) is not None
    assert registry.get_processor(Path("test.js")) is not None
    assert registry.get_processor(Path("test.css")) is not None


# --- Asset Resolver Tests ---


def test_asset_resolver_js(tmp_path):
    """Test DefaultAssetPathResolver resolves JS paths."""
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (tmp_path / "assets" / "js").mkdir(parents=True)
    (tmp_path / "assets" / "js" / "app.js").write_text("js")

    resolver = DefaultAssetPathResolver(site_dir)
    assert resolver.js_path("app") == "/assets/js/app.js"
    assert resolver.js_path("app.js") == "/assets/js/app.js"


def test_asset_resolver_css(tmp_path):
    """Test DefaultAssetPathResolver resolves CSS paths."""
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (tmp_path / "assets" / "css").mkdir(parents=True)
    (tmp_path / "assets" / "css" / "main.css").write_text("css")

    resolver = DefaultAssetPathResolver(site_dir)
    assert resolver.css_path("main") == "/assets/css/main.css"


def test_asset_resolver_image_auto_detect(tmp_path):
    """Test DefaultAssetPathResolver auto-detects image extension."""
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (tmp_path / "assets" / "images").mkdir(parents=True)
    (tmp_path / "assets" / "images" / "logo.png").write_text("img")

    resolver = DefaultAssetPathResolver(site_dir)
    assert resolver.img_path("logo") == "/assets/images/logo.png"


def test_asset_resolver_font_auto_detect(tmp_path):
    """Test DefaultAssetPathResolver auto-detects font extension."""
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (tmp_path / "assets" / "fonts").mkdir(parents=True)
    (tmp_path / "assets" / "fonts" / "inter.woff2").write_text("font")

    resolver = DefaultAssetPathResolver(site_dir)
    assert resolver.font_path("inter") == "/assets/fonts/inter.woff2"


def test_asset_resolver_missing():
    """Test DefaultAssetPathResolver raises for missing assets."""
    resolver = DefaultAssetPathResolver(Path("/nonexistent"))
    with pytest.raises(AssetNotFoundError):
        resolver.js_path("missing")


def test_asset_resolver_with_url_generator(tmp_path):
    """Test DefaultAssetPathResolver with custom URL generator."""
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (tmp_path / "assets" / "js").mkdir(parents=True)
    (tmp_path / "assets" / "js" / "app.js").write_text("js")

    resolver = DefaultAssetPathResolver(site_dir)
    resolver.set_url_generator(lambda x: f"https://example.com{x}")
    assert resolver.js_path("app") == "https://example.com/assets/js/app.js"


def test_asset_resolver_resolve_method(tmp_path):
    """Test DefaultAssetPathResolver.resolve() method."""
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (tmp_path / "assets" / "js").mkdir(parents=True)
    (tmp_path / "assets" / "js" / "app.js").write_text("js")

    resolver = DefaultAssetPathResolver(site_dir)
    assert resolver.resolve("app", "js") == "/assets/js/app.js"

    with pytest.raises(ValueError):
        resolver.resolve("test", "unknown")


# --- Content Module Tests ---


def test_file_content_loader(tmp_path):
    """Test FileContentLoader discovers content files."""
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (site_dir / "index.md").write_text("# Home")
    (site_dir / "_draft.md").write_text("# Draft")
    (site_dir / "_layouts").mkdir()

    loader = FileContentLoader(site_dir)
    files = loader.iter_files(include_drafts=False)
    assert len(files) == 1
    assert files[0].name == "index.md"

    files_with_drafts = loader.iter_files(include_drafts=True)
    assert len(files_with_drafts) == 2


def test_layout_resolver(tmp_path):
    """Test LayoutResolver resolves layouts."""
    site_dir = tmp_path / "site"
    (site_dir / "_layouts").mkdir(parents=True)
    (site_dir / "_layouts" / "default.html.jinja").write_text("default")
    (site_dir / "_layouts" / "posts.html.jinja").write_text("posts")

    resolver = LayoutResolver(site_dir)
    assert resolver.resolve(Path("test.md"), "") == "default"
    assert resolver.resolve(Path("test.md"), "posts") == "posts"


def test_url_deriver():
    """Test UrlDeriver generates correct URLs."""
    deriver = UrlDeriver()
    assert deriver.derive(Path("index.md"), "index") == "/"
    assert deriver.derive(Path("about.md"), "about") == "/about/"
    assert deriver.derive(Path("posts/hello.md"), "hello") == "/posts/hello/"


def test_default_page_builder(tmp_path):
    """Test DefaultPageBuilder creates Page objects."""
    site_dir = tmp_path / "site"
    (site_dir / "_layouts").mkdir(parents=True)
    (site_dir / "_layouts" / "default.html.jinja").write_text("default")
    (site_dir / "test.md").write_text("# Test\n\nContent here.")

    builder = DefaultPageBuilder(site_dir)
    page = builder.build(site_dir / "test.md", draft=False)
    assert page.title == "Test"
    assert page.source_type == "markdown"


def test_content_processor_with_custom_components(tmp_path):
    """Test ContentProcessor accepts custom components."""
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (site_dir / "_layouts").mkdir()
    (site_dir / "_layouts" / "default.html.jinja").write_text("default")
    (site_dir / "test.md").write_text("# Test")

    loader = FileContentLoader(site_dir)
    builder = DefaultPageBuilder(site_dir)
    processor = ContentProcessor(site_dir, content_loader=loader, page_builder=builder)

    pages = processor.load()
    assert len(pages) == 1


# --- Protocol Tests (verify implementations match protocols) ---


def test_renderer_implements_protocol():
    """Verify renderers implement ContentRenderer protocol."""
    from medusa.protocols import ContentRenderer

    assert isinstance(MarkdownRenderer(), ContentRenderer)
    assert isinstance(HTMLRenderer(), ContentRenderer)
    assert isinstance(JinjaContentRenderer(), ContentRenderer)


def test_extractor_implements_protocol():
    """Verify extractors implement MetadataExtractor protocol."""
    from medusa.protocols import MetadataExtractor

    assert isinstance(TitleExtractor(), MetadataExtractor)
    assert isinstance(TagExtractor(), MetadataExtractor)
    assert isinstance(DateExtractor(), MetadataExtractor)


def test_asset_processor_implements_protocol():
    """Verify processors implement AssetProcessor protocol."""
    from medusa.protocols import AssetProcessor

    assert isinstance(ImageProcessor(), AssetProcessor)
    assert isinstance(CSSProcessor(), AssetProcessor)
    assert isinstance(StaticAssetProcessor(), AssetProcessor)


# --- Additional Coverage Tests ---


def test_asset_resolver_resolve_css(tmp_path):
    """Test resolve method for CSS."""
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (tmp_path / "assets" / "css").mkdir(parents=True)
    (tmp_path / "assets" / "css" / "style.css").write_text("css")

    resolver = DefaultAssetPathResolver(site_dir)
    assert resolver.resolve("style", "css") == "/assets/css/style.css"


def test_asset_resolver_resolve_image(tmp_path):
    """Test resolve method for images."""
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (tmp_path / "assets" / "images").mkdir(parents=True)
    (tmp_path / "assets" / "images" / "logo.png").write_text("img")

    resolver = DefaultAssetPathResolver(site_dir)
    assert resolver.resolve("logo", "image") == "/assets/images/logo.png"


def test_asset_resolver_resolve_font(tmp_path):
    """Test resolve method for fonts."""
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (tmp_path / "assets" / "fonts").mkdir(parents=True)
    (tmp_path / "assets" / "fonts" / "inter.woff2").write_text("font")

    resolver = DefaultAssetPathResolver(site_dir)
    assert resolver.resolve("inter", "font") == "/assets/fonts/inter.woff2"


def test_image_processor_pil_exception(tmp_path, monkeypatch):
    """Test ImageProcessor when PIL raises exception."""
    from PIL import Image

    def mock_open(*args, **kwargs):
        raise Exception("PIL error")

    monkeypatch.setattr(Image, "open", mock_open)

    processor = ImageProcessor()
    source = tmp_path / "source.png"
    source.write_text("fake")
    dest = tmp_path / "out" / "dest.png"

    processor.process(source, dest)
    assert dest.exists()


def test_tailwind_processor_with_cli(tmp_path, monkeypatch):
    """Test TailwindCSSProcessor with CLI available."""
    import subprocess

    def mock_which(name):
        return "/usr/bin/tailwindcss"

    def mock_run(cmd, capture_output=None, text=None):
        # Simulate successful build
        dest = Path(cmd[4])
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("built css")
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr("shutil.which", mock_which)
    monkeypatch.setattr("subprocess.run", mock_run)

    processor = TailwindCSSProcessor(tmp_path, tmp_path / "out")
    source = tmp_path / "main.css"
    source.write_text("@tailwind base;")
    dest = tmp_path / "out" / "main.css"

    processor.process(source, dest)
    assert dest.exists()


def test_tailwind_processor_failure(tmp_path, monkeypatch, capsys):
    """Test TailwindCSSProcessor handles build failure."""
    import subprocess

    def mock_which(name):
        return "/usr/bin/tailwindcss"

    def mock_run(cmd, capture_output=None, text=None):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="error")

    monkeypatch.setattr("shutil.which", mock_which)
    monkeypatch.setattr("subprocess.run", mock_run)

    processor = TailwindCSSProcessor(tmp_path, tmp_path / "out")
    source = tmp_path / "main.css"
    source.write_text("@tailwind base;")
    dest = tmp_path / "out" / "main.css"

    processor.process(source, dest)
    # Falls back to copying
    assert dest.exists()


def test_tailwind_processor_local_binary(tmp_path, monkeypatch):
    """Test TailwindCSSProcessor finds local node_modules binary."""
    import subprocess

    # No global binary
    monkeypatch.setattr("shutil.which", lambda x: None)

    # Create local binary
    local_bin = tmp_path / "node_modules" / ".bin" / "tailwindcss"
    local_bin.parent.mkdir(parents=True)
    local_bin.write_text("#!/bin/sh\necho ok")

    def mock_run(cmd, capture_output=None, text=None):
        dest = Path(cmd[4])
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("built css")
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr("subprocess.run", mock_run)

    processor = TailwindCSSProcessor(tmp_path, tmp_path / "out")
    source = tmp_path / "main.css"
    source.write_text("@tailwind base;")
    (tmp_path / "assets" / "css").mkdir(parents=True)
    dest = tmp_path / "out" / "main.css"

    processor.process(source, dest)
    assert dest.exists()


def test_js_processor_terser_failure(tmp_path, monkeypatch, capsys):
    """Test JSProcessor handles terser failure."""
    import subprocess

    monkeypatch.setattr("medusa.asset_processors.jsmin", None)

    # Create local terser binary
    terser_bin = tmp_path / "node_modules" / ".bin" / "terser"
    terser_bin.parent.mkdir(parents=True)
    terser_bin.write_text("#!/bin/sh\nexit 1")

    def mock_run(cmd, capture_output=None, text=None):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="terser error")

    monkeypatch.setattr("subprocess.run", mock_run)

    processor = JSProcessor(tmp_path)
    source = tmp_path / "app.js"
    source.write_text("function test() { return 1; }")
    dest = tmp_path / "out" / "app.js"

    processor.process(source, dest)
    # Falls back to copying
    assert dest.exists()
    captured = capsys.readouterr()
    assert "JS minification failed" in captured.out


def test_asset_registry_process_no_processor():
    """Test AssetProcessorRegistry.process() when no processor found."""
    registry = AssetProcessorRegistry()
    # Don't register any processors
    result = registry.process(Path("test.xyz"), Path("out.xyz"))
    assert result is False


def test_content_processor_unknown_source_type(tmp_path):
    """Test DefaultPageBuilder with unknown file type."""
    site_dir = tmp_path / "site"
    (site_dir / "_layouts").mkdir(parents=True)
    (site_dir / "_layouts" / "default.html.jinja").write_text("default")

    # Create an unknown file type
    test_file = site_dir / "test.xyz"
    test_file.write_text("content")

    builder = DefaultPageBuilder(site_dir)
    # This should handle unknown file types gracefully
    page = builder.build(test_file, draft=False)
    assert page.source_type == "unknown"


def test_templates_render_string(tmp_path):
    """Test TemplateEngine.render_string() method."""
    from medusa.templates import TemplateEngine

    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (site_dir / "_layouts").mkdir()
    (site_dir / "_partials").mkdir()

    engine = TemplateEngine(site_dir, {"title": "Test"})
    result = engine.render_string(
        "Hello {{ data.title }}", {"data": {"title": "World"}}
    )
    assert result == "Hello World"


def test_js_processor_jsmin_exception(tmp_path, monkeypatch):
    """Test JSProcessor handles jsmin exception."""

    def mock_jsmin(content):
        raise Exception("jsmin error")

    monkeypatch.setattr("medusa.asset_processors.jsmin", mock_jsmin)
    monkeypatch.setattr("shutil.which", lambda x: None)

    processor = JSProcessor(tmp_path)
    source = tmp_path / "app.js"
    source.write_text("function test() { return 1; }")
    dest = tmp_path / "out" / "app.js"

    processor.process(source, dest)
    # Falls back to copying
    assert dest.exists()
    assert "function test" in dest.read_text()


def test_js_processor_terser_success(tmp_path, monkeypatch):
    """Test JSProcessor uses terser successfully."""
    import subprocess

    monkeypatch.setattr("medusa.asset_processors.jsmin", None)
    monkeypatch.setattr("shutil.which", lambda x: "/usr/bin/terser")

    def mock_run(cmd, capture_output=None, text=None):
        dest = Path(cmd[cmd.index("-o") + 1])
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("minified")
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr("subprocess.run", mock_run)

    processor = JSProcessor(tmp_path)
    source = tmp_path / "app.js"
    source.write_text("function test() { return 1; }")
    dest = tmp_path / "out" / "app.js"

    processor.process(source, dest)
    assert dest.exists()
    assert dest.read_text() == "minified"


def test_content_processor_rewrite_inline_images(tmp_path):
    """Test ContentProcessor._rewrite_inline_images backward compatibility."""
    from medusa.content import ContentProcessor

    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (site_dir / "_layouts").mkdir()

    processor = ContentProcessor(site_dir)
    html = '<p><img src="photo.png"></p>'
    rewritten = processor._rewrite_inline_images(html, "gallery")
    assert "/assets/images/gallery/photo.png" in rewritten


def test_content_processor_iter_source_files(tmp_path):
    """Test ContentProcessor._iter_source_files backward compatibility."""
    from medusa.content import ContentProcessor

    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (site_dir / "_layouts").mkdir()
    (site_dir / "test.md").write_text("# Test")

    processor = ContentProcessor(site_dir)
    files = list(processor._iter_source_files(include_drafts=False))
    assert len(files) == 1
    assert files[0].name == "test.md"
