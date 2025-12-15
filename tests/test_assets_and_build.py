import io
import shutil
import subprocess
from pathlib import Path

import pytest

from medusa.assets import AssetPipeline
from medusa.build import BuildResult, build_site, load_config, load_data


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

    (project / "medusa.yaml").write_text("output_dir: output\nport: 4000\n", encoding="utf-8")
    (project / "data" / "site.yaml").write_text("title: Test\nurl: https://example.com\n", encoding="utf-8")
    (project / "data" / "nav.yaml").write_text("- label: Home\n  url: /\n", encoding="utf-8")
    (site / "_layouts" / "default.html.jinja").write_text("{{ page_content }}", encoding="utf-8")
    (site / "index.md").write_text("# Hello\n\nWelcome!", encoding="utf-8")
    (project / "assets" / "css" / "main.css").write_text("@tailwind base;", encoding="utf-8")
    (project / "assets" / "js" / "main.js").write_text("function test(){ return 1 + 1; }", encoding="utf-8")

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
    pipeline._process_tailwind()
    assert calls["which"] == "tailwindcss"


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


def test_minify_js_skips_when_missing(monkeypatch, tmp_path):
    project = create_project(tmp_path)
    output = project / "out"
    pipeline = AssetPipeline(project, output)
    monkeypatch.setattr("medusa.assets.jsmin", None)
    pipeline._minify_js()
    # no files should be written because jsmin is unavailable
    assert not (output / "assets").exists()


def test_build_site_creates_output(monkeypatch, tmp_path):
    project = create_project(tmp_path)

    result = build_site(project, include_drafts=False)
    assert isinstance(result, BuildResult)
    index = result.output_dir / "index.html"
    assert index.exists()

    sitemap = result.output_dir / "sitemap.xml"
    rss = result.output_dir / "rss.xml"
    assert sitemap.exists()
    assert rss.exists()

    config = load_config(project)
    data = load_data(project)
    assert config["output_dir"] == "output"
    assert data["title"] == "Test"


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
