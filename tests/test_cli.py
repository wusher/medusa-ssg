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

    def fake_build_site(root, include_drafts=False):
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
