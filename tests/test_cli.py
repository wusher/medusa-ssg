from pathlib import Path
import subprocess

from click.testing import CliRunner

from medusa.cli import cli
from medusa.build import BuildResult


def test_cli_new_scaffolds_project(tmp_path):
    runner = CliRunner()
    target = tmp_path / "mysite"
    result = runner.invoke(cli, ["new", str(target)], env={"MEDUSA_SKIP_NPM_INSTALL": "1"})
    assert result.exit_code == 0
    assert (target / "site" / "index.jinja").exists()
    assert (target / "site" / "posts" / "index.jinja").exists()
    assert (target / "assets" / "css" / "main.css").exists()
    package_json = (target / "package.json").read_text(encoding="utf-8")
    assert "tailwindcss" in package_json
    assert "terser" in package_json

    # fails on non-empty directory
    (target / "extra.txt").write_text("x", encoding="utf-8")
    result = runner.invoke(cli, ["new", str(target)], env={"MEDUSA_SKIP_NPM_INSTALL": "1"})
    assert result.exit_code != 0


def test_cli_build_and_serve(monkeypatch, tmp_path):
    runner = CliRunner()
    project = tmp_path / "mysite"
    runner.invoke(cli, ["new", str(project)], env={"MEDUSA_SKIP_NPM_INSTALL": "1"})
    monkeypatch.chdir(project)

    def fake_build_site(root, include_drafts=False, root_url=None, clean_output=True, output_dir_override=None):
        out = root / "output"
        out.mkdir()
        return BuildResult(pages=[], output_dir=out, data={})

    called = {}

    class DummyServer:
        def __init__(self, root, http_port=None, ws_port=None):
            self.root = root
            self.started = False
            called["port"] = http_port
            called["ws_port"] = ws_port

        def start(self, include_drafts=False):
            self.started = include_drafts

    monkeypatch.setattr("medusa.build.build_site", fake_build_site)
    monkeypatch.setattr("medusa.server.DevServer", DummyServer)

    result = runner.invoke(cli, ["build"], catch_exceptions=False)
    assert result.exit_code == 0

    result = runner.invoke(
        cli, ["serve", "--drafts", "--port", "5050", "--ws-port", "5051"], catch_exceptions=False
    )
    assert result.exit_code == 0
    assert called["port"] == 5050
    assert called["ws_port"] == 5051


def test_module_main_entrypoint():
    from medusa.__main__ import main

    assert callable(main)


def test_main_invokes_cli(monkeypatch):
    import medusa.cli as cli_mod

    called = {}

    def fake_cli():
        called["ran"] = True

    original_cli = cli_mod.cli
    cli_mod.cli = fake_cli
    try:
        cli_mod.main()
    finally:
        cli_mod.cli = original_cli
    assert called["ran"]


def test_try_npm_install(monkeypatch, tmp_path):
    from medusa.cli import _try_npm_install

    called = {}
    monkeypatch.setenv("MEDUSA_SKIP_NPM_INSTALL", "0")
    monkeypatch.setattr("medusa.cli.shutil.which", lambda cmd: "/usr/bin/npm")

    def fake_run(cmd, cwd=None, check=None, stdout=None, stderr=None):
        called["cmd"] = cmd
        called["cwd"] = cwd
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr("medusa.cli.subprocess.run", fake_run)
    _try_npm_install(tmp_path)
    assert called["cmd"][0].endswith("npm")
    assert called["cwd"] == tmp_path


def test_try_npm_install_missing(monkeypatch, tmp_path):
    from medusa.cli import _try_npm_install

    monkeypatch.setattr("medusa.cli.shutil.which", lambda cmd: None)
    _try_npm_install(tmp_path)  # should no-op without error


def test_try_npm_install_failure(monkeypatch, tmp_path):
    from medusa.cli import _try_npm_install

    monkeypatch.setattr("medusa.cli.shutil.which", lambda cmd: "/usr/bin/npm")

    def fake_run(cmd, cwd=None, check=None, stdout=None, stderr=None):
        raise RuntimeError("boom")

    monkeypatch.setattr("medusa.cli.subprocess.run", fake_run)
    _try_npm_install(tmp_path)  # should swallow exception


def test_md_helper_functions(tmp_path):
    """Test the helper functions for the md command."""
    from medusa.cli import _get_content_folders, _get_existing_slugs, _extract_slug, _titleize

    # Set up test directory structure
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (site_dir / "posts").mkdir()
    (site_dir / "pages").mkdir()
    (site_dir / "_layouts").mkdir()  # Should be excluded
    (site_dir / "_partials").mkdir()  # Should be excluded

    # Test _get_content_folders
    folders = _get_content_folders(site_dir)
    assert ". (root)" in folders
    assert "posts" in folders
    assert "pages" in folders
    assert "_layouts" not in folders
    assert "_partials" not in folders

    # Test _extract_slug
    assert _extract_slug("my-post.md") == "my-post"
    assert _extract_slug("2024-01-15-my-post.md") == "my-post"
    assert _extract_slug("2024-12-18-hello-world.md") == "hello-world"
    assert _extract_slug("simple.md") == "simple"

    # Test _get_existing_slugs
    posts_dir = site_dir / "posts"
    (posts_dir / "2024-01-01-first-post.md").write_text("# First", encoding="utf-8")
    (posts_dir / "second-post.md").write_text("# Second", encoding="utf-8")
    slugs = _get_existing_slugs(posts_dir)
    assert "first-post" in slugs
    assert "second-post" in slugs

    # Test _titleize
    assert _titleize("my-post") == "My Post"
    assert _titleize("hello_world") == "Hello World"
    assert _titleize("simple") == "Simple"


def test_md_command_no_site_dir(tmp_path, monkeypatch):
    """Test md command fails when no site directory exists."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(cli, ["md"])
    assert result.exit_code != 0
    assert "No site/ directory found" in result.output


def test_md_command_creates_file(tmp_path, monkeypatch):
    """Test md command creates a markdown file."""
    runner = CliRunner()

    # Set up project structure
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (site_dir / "posts").mkdir()

    monkeypatch.chdir(tmp_path)

    # Mock questionary prompts
    responses = iter(["posts", "my-new-post", True])

    def mock_select(*args, **kwargs):
        class MockQuestion:
            def ask(self):
                return next(responses)
        return MockQuestion()

    def mock_text(*args, **kwargs):
        class MockQuestion:
            def ask(self):
                return next(responses)
        return MockQuestion()

    def mock_confirm(*args, **kwargs):
        class MockQuestion:
            def ask(self):
                return next(responses)
        return MockQuestion()

    monkeypatch.setattr("medusa.cli.questionary.select", mock_select)
    monkeypatch.setattr("medusa.cli.questionary.text", mock_text)
    monkeypatch.setattr("medusa.cli.questionary.confirm", mock_confirm)

    result = runner.invoke(cli, ["md"], catch_exceptions=False)
    assert result.exit_code == 0

    # Check file was created with date prefix
    from datetime import datetime
    date_prefix = datetime.now().strftime("%Y-%m-%d")
    expected_file = site_dir / "posts" / f"{date_prefix}-my-new-post.md"
    assert expected_file.exists()
    content = expected_file.read_text(encoding="utf-8")
    assert "# My New Post" in content


def test_md_command_duplicate_detection(tmp_path, monkeypatch):
    """Test md command detects duplicate slugs."""
    runner = CliRunner()

    # Set up project structure with existing file
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    posts_dir = site_dir / "posts"
    posts_dir.mkdir()
    (posts_dir / "2024-01-01-existing-post.md").write_text("# Existing", encoding="utf-8")

    monkeypatch.chdir(tmp_path)

    # Mock questionary to try creating a file with same slug
    responses = iter(["posts", "existing-post", True])

    def mock_select(*args, **kwargs):
        class MockQuestion:
            def ask(self):
                return next(responses)
        return MockQuestion()

    def mock_text(*args, **kwargs):
        class MockQuestion:
            def ask(self):
                return next(responses)
        return MockQuestion()

    def mock_confirm(*args, **kwargs):
        class MockQuestion:
            def ask(self):
                return next(responses)
        return MockQuestion()

    monkeypatch.setattr("medusa.cli.questionary.select", mock_select)
    monkeypatch.setattr("medusa.cli.questionary.text", mock_text)
    monkeypatch.setattr("medusa.cli.questionary.confirm", mock_confirm)

    result = runner.invoke(cli, ["md"])
    assert result.exit_code != 0
    assert "already exists" in result.output
