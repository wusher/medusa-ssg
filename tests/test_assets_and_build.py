import shutil
import subprocess
from pathlib import Path

import pytest

from medusa.assets import AssetPipeline
from medusa.build import (
    BuildError,
    BuildResult,
    _format_error_message,
    build_site,
    load_config,
    load_data,
)


def create_project(tmp_path: Path) -> Path:
    project = tmp_path
    site = project / "site"
    (site / "_layouts").mkdir(parents=True)
    (site / "_partials").mkdir()
    (site / "posts").mkdir()
    (project / "assets" / "css").mkdir(parents=True)
    (project / "assets" / "js").mkdir(parents=True)
    (project / "assets" / "images").mkdir(parents=True)
    (project / "data").mkdir()

    (project / "medusa.yaml").write_text(
        "output_dir: output\nport: 4000\nroot_url: https://example.com\n",
        encoding="utf-8",
    )
    (project / "data" / "site.yaml").write_text(
        "title: Test\nurl: https://example.com\n", encoding="utf-8"
    )
    (project / "data" / "nav.yaml").write_text(
        "- label: Home\n  url: /\n", encoding="utf-8"
    )
    (site / "_layouts" / "default.html.jinja").write_text(
        "<link rel='stylesheet' href=\"{{ url_for('/assets/css/main.css') }}\">{{ page_content }}",
        encoding="utf-8",
    )
    (site / "index.md").write_text(
        "# Hello\n\nWelcome!\n\n[About](/about/)", encoding="utf-8"
    )
    (project / "assets" / "css" / "main.css").write_text(
        "@tailwind base;", encoding="utf-8"
    )
    (project / "assets" / "js" / "main.js").write_text(
        "function test(){ return 1 + 1; }", encoding="utf-8"
    )

    # Pillow available; write tiny image
    from PIL import Image

    img = Image.new("RGB", (2, 2), color="red")
    img.save(project / "assets" / "images" / "logo.png")

    return project


def test_asset_pipeline_runs_without_tailwind(monkeypatch, tmp_path):
    project = create_project(tmp_path)
    output = project / "out"
    pipeline = AssetPipeline(project, output)

    calls = {}

    def fake_which(cmd):
        calls["which"] = cmd
        return None

    monkeypatch.setattr(shutil, "which", fake_which)
    # also simulate node_modules/.bin missing
    (project / "node_modules" / ".bin").mkdir(parents=True, exist_ok=True)
    pipeline._process_tailwind()
    assert calls["which"] == "tailwindcss"

    # simulate node_modules binary present
    tailwind_bin = project / "node_modules" / ".bin" / "tailwindcss"
    tailwind_bin.write_text("#!/bin/sh\necho ok\n", encoding="utf-8")
    seen = {}

    def fake_run(cmd, capture_output=None, text=None):
        seen["bin"] = cmd[0]
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    pipeline._process_tailwind()
    assert seen["bin"] == str(tailwind_bin)


def test_js_minify_prefers_terser(monkeypatch, tmp_path):
    project = create_project(tmp_path)
    output = project / "out"
    pipeline = AssetPipeline(project, output)
    monkeypatch.setattr("medusa.assets.jsmin", None)

    terser_bin = project / "node_modules" / ".bin" / "terser"
    terser_bin.parent.mkdir(parents=True, exist_ok=True)
    terser_bin.write_text("#!/bin/sh\necho terser\n", encoding="utf-8")

    calls = {}

    def fake_run(cmd, capture_output=None, text=None):
        calls["cmd"] = cmd
        dest_index = cmd.index("-o") + 1
        Path(cmd[dest_index]).write_text("minified", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    pipeline._minify_js()
    assert calls["cmd"][0] == str(terser_bin)


def test_js_minify_terser_failure(monkeypatch, tmp_path, capsys):
    project = create_project(tmp_path)
    output = project / "out"
    pipeline = AssetPipeline(project, output)
    monkeypatch.setattr("medusa.assets.jsmin", None)

    terser_bin = project / "node_modules" / ".bin" / "terser"
    terser_bin.parent.mkdir(parents=True, exist_ok=True)
    terser_bin.write_text("#!/bin/sh\necho terser\n", encoding="utf-8")

    def fake_run(cmd, capture_output=None, text=None):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="fail")

    monkeypatch.setattr(subprocess, "run", fake_run)
    pipeline._minify_js()
    out = capsys.readouterr()
    assert "JS minification failed via terser" in out.out


def test_asset_pipeline_with_tailwind(monkeypatch, tmp_path):
    project = create_project(tmp_path)
    output = project / "out"
    pipeline = AssetPipeline(project, output)

    fake_bin = project / "bin" / "tailwindcss"
    fake_bin.parent.mkdir()
    fake_bin.write_text("#!/bin/sh\necho built\n", encoding="utf-8")

    def fake_run(cmd, capture_output=None, text=None):
        # simulate Tailwind writing output
        out_path = Path(cmd[4])
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("body{}", encoding="utf-8")
        cp = subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")
        return cp

    monkeypatch.setattr(shutil, "which", lambda _: str(fake_bin))
    monkeypatch.setattr(subprocess, "run", fake_run)
    pipeline.run()

    css_out = output / "assets" / "css" / "main.css"
    assert css_out.exists() and css_out.read_text() == "body{}"
    js_out = output / "assets" / "js" / "main.js"
    assert js_out.read_text().strip() == "function test(){return 1+1;}"
    image_out = output / "assets" / "images" / "logo.png"
    assert image_out.exists()


def test_asset_pipeline_missing_assets(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    output = project / "out"
    pipeline = AssetPipeline(project, output)
    pipeline.run()  # should no-op
    assert not output.exists()


def test_tailwind_missing_input(monkeypatch, tmp_path):
    project = tmp_path / "proj"
    (project / "assets").mkdir(parents=True)
    pipeline = AssetPipeline(project, project / "out")
    # no main.css present -> early return
    pipeline._process_tailwind()


def test_tailwind_failure(monkeypatch, tmp_path, capsys):
    project = create_project(tmp_path)
    output = project / "out"
    pipeline = AssetPipeline(project, output)

    monkeypatch.setattr(shutil, "which", lambda _: "tailwindcss")

    def fake_run(cmd, capture_output=None, text=None):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="boom")

    monkeypatch.setattr(subprocess, "run", fake_run)
    pipeline._process_tailwind()
    captured = capsys.readouterr()
    assert "Tailwind build failed" in captured.out
    assert (output / "assets" / "css" / "main.css").exists()


def test_minify_js_skips_when_missing(monkeypatch, tmp_path):
    project = create_project(tmp_path)
    output = project / "out"
    pipeline = AssetPipeline(project, output)
    monkeypatch.setattr("medusa.assets.jsmin", None)
    pipeline._minify_js()
    js_out = output / "assets" / "js" / "main.js"
    assert js_out.exists()
    assert "return 1 + 1" in js_out.read_text()


def test_build_site_creates_output(monkeypatch, tmp_path):
    project = create_project(tmp_path)

    result = build_site(project, include_drafts=False)
    assert isinstance(result, BuildResult)
    index = result.output_dir / "index.html"
    assert index.exists()
    html = index.read_text(encoding="utf-8")
    assert "https://example.com/assets/css/main.css" in html
    assert "https://example.com/about/" in html

    sitemap = result.output_dir / "sitemap.xml"
    rss = result.output_dir / "rss.xml"
    assert sitemap.exists()
    assert rss.exists()

    config = load_config(project)
    data = load_data(project)
    assert config["output_dir"] == "output"
    assert data["title"] == "Test"


def test_build_processes_html_files(tmp_path):
    """HTML files are now processed as pages with pretty URLs."""
    project = create_project(tmp_path)
    static_html = project / "site" / "static" / "plain.html"
    static_html.parent.mkdir(parents=True, exist_ok=True)
    static_html.write_text("<html><body>plain</body></html>", encoding="utf-8")
    hidden_html = project / "site" / "_hidden" / "secret.html"
    hidden_html.parent.mkdir(parents=True, exist_ok=True)
    hidden_html.write_text("<html>secret</html>", encoding="utf-8")

    result = build_site(project, include_drafts=False)
    # HTML files are now processed as pages with pretty URLs
    out_file = result.output_dir / "static" / "plain" / "index.html"
    assert out_file.exists()
    assert "plain" in out_file.read_text(encoding="utf-8")
    # Hidden files are still excluded
    assert not (result.output_dir / "_hidden" / "secret" / "index.html").exists()


def test_build_root_url_override(tmp_path):
    project = create_project(tmp_path)
    result = build_site(project, include_drafts=False, root_url="https://override.com")
    html = (result.output_dir / "index.html").read_text(encoding="utf-8")
    assert "https://override.com/assets/css/main.css" in html
    assert "https://override.com/about/" in html


def test_build_without_root_url(tmp_path):
    project = create_project(tmp_path)
    # wipe root_url and site url to force relative output
    (project / "medusa.yaml").write_text(
        "output_dir: output\nport: 4000\n", encoding="utf-8"
    )
    (project / "data" / "site.yaml").write_text("title: Test\n", encoding="utf-8")
    static_html = project / "site" / "static" / "plain.html"
    static_html.parent.mkdir(parents=True, exist_ok=True)
    static_html.write_text("<html><body>plain</body></html>", encoding="utf-8")
    result = build_site(project, include_drafts=False)
    html = (result.output_dir / "index.html").read_text(encoding="utf-8")
    assert 'href="/assets/css/main.css"' in html
    assert 'href="/about/"' in html
    # HTML files are now processed as pages with pretty URLs (wrapped in layout)
    plain_content = (result.output_dir / "static" / "plain" / "index.html").read_text(
        encoding="utf-8"
    )
    assert "plain" in plain_content


def test_build_helpers_handle_missing(monkeypatch, tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    config = load_config(project)
    assert config["output_dir"] == "output"

    (project / "medusa.yaml").write_text("- not a dict", encoding="utf-8")
    config = load_config(project)
    assert config["output_dir"] == "output"

    data = load_data(project)
    assert data == {}

    (project / "data").mkdir()
    (project / "data" / "bad.yaml").write_text("- list", encoding="utf-8")
    assert load_data(project) == {}
    (project / "data" / "extra.yaml").write_text("foo: bar", encoding="utf-8")
    assert load_data(project)["extra"] == {"foo": "bar"}

    # _write_sitemap and _write_rss bail when url missing
    from medusa.build import _write_rss, _write_sitemap

    out = project / "out"
    out.mkdir()
    _write_sitemap(out, {}, [])
    _write_rss(out, {}, [])
    assert not (out / "sitemap.xml").exists()
    assert not (out / "rss.xml").exists()

    with pytest.raises(FileNotFoundError):
        build_site(project)


def test_build_site_without_clean_output(tmp_path):
    """Test build_site with clean_output=False creates output dir if missing."""
    project = create_project(tmp_path)
    output_override = tmp_path / "custom_output"

    # First build with clean_output=False - should create the directory
    result = build_site(
        project,
        include_drafts=False,
        clean_output=False,
        output_dir_override=output_override,
    )
    assert result.output_dir == output_override
    assert (output_override / "index.html").exists()

    # Build again with clean_output=False - should preserve existing files
    marker = output_override / "marker.txt"
    marker.write_text("preserved", encoding="utf-8")
    result = build_site(
        project,
        include_drafts=False,
        clean_output=False,
        output_dir_override=output_override,
    )
    # File should still exist since we didn't clean
    assert marker.exists()


def test_build_error_exception():
    """Test BuildError exception contains file context."""
    source = Path("/some/path/page.md")
    error = BuildError(source, "Something went wrong", ValueError("original"))
    assert error.source_path == source
    assert error.message == "Something went wrong"
    assert isinstance(error.original_error, ValueError)
    assert "/some/path/page.md" in str(error)
    assert "Something went wrong" in str(error)


def test_format_error_message():
    """Test _format_error_message formats different exception types."""

    # UndefinedError
    class UndefinedError(Exception):
        pass

    err = UndefinedError("'foo' is undefined")
    err.__class__.__name__ = "UndefinedError"
    assert "Undefined variable" in _format_error_message(err)

    # TypeError
    err = TypeError("sorted() got an unexpected keyword argument 'key'")
    assert "Type error" in _format_error_message(err)

    # AttributeError
    err = AttributeError("'NoneType' has no attribute 'bar'")
    assert "Attribute error" in _format_error_message(err)

    # Generic error
    err = RuntimeError("something else")
    result = _format_error_message(err)
    assert "RuntimeError" in result
    assert "something else" in result


def test_build_site_template_error(tmp_path):
    """Test build_site raises BuildError with file context on template errors."""
    project = create_project(tmp_path)
    # Create a page with invalid Jinja2 template syntax
    bad_page = project / "site" / "broken.html.jinja"
    bad_page.write_text("{{ undefined_var.nonexistent }}", encoding="utf-8")

    with pytest.raises(BuildError) as exc_info:
        build_site(project)

    assert exc_info.value.source_path == bad_page
    assert exc_info.value.original_error is not None


def test_build_site_template_syntax_error(tmp_path):
    """Test build_site raises BuildError for template syntax errors."""
    project = create_project(tmp_path)
    # Create a page with invalid Jinja2 syntax
    bad_page = project / "site" / "broken.html.jinja"
    bad_page.write_text("{% for x in items %}\nNo end!", encoding="utf-8")

    with pytest.raises(BuildError) as exc_info:
        build_site(project)

    assert exc_info.value.source_path == bad_page
    assert "syntax error" in exc_info.value.message.lower()
