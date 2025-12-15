from pathlib import Path

from click.testing import CliRunner

from medusa.cli import cli
from medusa.build import BuildResult


def test_cli_new_scaffolds_project(tmp_path):
    runner = CliRunner()
    target = tmp_path / "mysite"
    result = runner.invoke(cli, ["new", str(target)])
    assert result.exit_code == 0
    assert (target / "site" / "index.md").exists()
    assert (target / "assets" / "css" / "main.css").exists()

    # fails on non-empty directory
    (target / "extra.txt").write_text("x", encoding="utf-8")
    result = runner.invoke(cli, ["new", str(target)])
    assert result.exit_code != 0


def test_cli_build_and_serve(monkeypatch, tmp_path):
    runner = CliRunner()
    project = tmp_path / "mysite"
    runner.invoke(cli, ["new", str(project)])
    monkeypatch.chdir(project)

    def fake_build_site(root, include_drafts=False):
        out = root / "output"
        out.mkdir()
        return BuildResult(pages=[], output_dir=out, data={})

    class DummyServer:
        def __init__(self, root):
            self.root = root
            self.started = False

        def start(self, include_drafts=False):
            self.started = include_drafts

    monkeypatch.setattr("medusa.build.build_site", fake_build_site)
    monkeypatch.setattr("medusa.server.DevServer", DummyServer)

    result = runner.invoke(cli, ["build"], catch_exceptions=False)
    assert result.exit_code == 0

    result = runner.invoke(cli, ["serve", "--drafts"], catch_exceptions=False)
    assert result.exit_code == 0


def test_module_main_entrypoint():
    from medusa.__main__ import main

    assert callable(main)
