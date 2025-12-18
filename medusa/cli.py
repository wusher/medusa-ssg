"""Command-line interface for Medusa.

This module defines the CLI commands using Click framework.
It provides commands for creating new projects, building sites, and running the development server.

Commands:
- new: Scaffold a new Medusa project.
- build: Build the site into the output directory.
- serve: Run development server with live reload.
"""

from __future__ import annotations

from pathlib import Path

import click
import json
import os
import shutil
import subprocess

from . import __version__


# Path to the default template directory
_TEMPLATES_DIR = Path(__file__).parent / "templates" / "default"


@click.group()
@click.version_option(version=__version__, prog_name="medusa")
def cli():
    """Medusa static site generator."""


@cli.command()
@click.argument("name")
def new(name: str):
    """Scaffold a new Medusa project."""
    target = Path(name).resolve()
    if target.exists() and any(target.iterdir()):
        raise click.ClickException(
            f"Refusing to initialize into non-empty directory: {target}"
        )
    _scaffold(target)
    click.echo(f"New Medusa site created at {target}")


@cli.command()
@click.option("--drafts", is_flag=True, help="Include draft content")
def build(drafts: bool):
    """Build the site into the output directory."""
    project_root = Path.cwd()
    from .build import build_site

    result = build_site(project_root, include_drafts=drafts)
    click.echo(f"Built {len(result.pages)} pages into {result.output_dir}")


@cli.command()
@click.option("--drafts", is_flag=True, help="Include draft content")
@click.option(
    "--port",
    type=int,
    required=False,
    help="Port to run the dev server (overrides medusa.yaml)",
)
@click.option(
    "--ws-port",
    type=int,
    required=False,
    help="Port for the live reload websocket server (overrides medusa.yaml ws_port)",
)
def serve(drafts: bool, port: int | None, ws_port: int | None):
    """Run dev server with live reload."""
    project_root = Path.cwd()
    from .server import DevServer

    server = DevServer(project_root, http_port=port, ws_port=ws_port)
    server.start(include_drafts=drafts)


def main():
    """Entry point for the CLI application."""
    cli()


def _scaffold(root: Path) -> None:
    """Create the directory structure and files for a new Medusa project.

    Args:
        root: Root directory for the new project.
    """
    # Copy template directory contents to new project
    for src_path in _TEMPLATES_DIR.rglob("*"):
        if src_path.is_dir():
            continue
        rel_path = src_path.relative_to(_TEMPLATES_DIR)
        dest_path = root / rel_path
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, dest_path)

    # Generate package.json with project name
    package_json = {
        "name": root.name,
        "private": True,
        "scripts": {
            "build:css": "tailwindcss -i assets/css/main.css -o output/assets/css/main.css --minify",
        },
        "devDependencies": {
            "@tailwindcss/typography": "^0.5.15",
            "tailwindcss": "^3.4.13",
            "terser": "^5.36.0",
        },
    }
    (root / "package.json").write_text(
        json.dumps(package_json, indent=2) + "\n", encoding="utf-8"
    )

    _try_npm_install(root)


def _try_npm_install(root: Path) -> None:
    """Attempt to install Node dependencies if npm is available."""
    if os.environ.get("MEDUSA_SKIP_NPM_INSTALL") == "1":
        return
    npm_bin = shutil.which("npm")
    if not npm_bin:
        return
    try:
        subprocess.run(
            [npm_bin, "install"],
            cwd=root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except Exception:
        # Non-fatal: user can run npm install manually
        pass
