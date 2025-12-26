"""Command-line interface for Medusa.

This module defines the CLI commands using Click framework.
It provides commands for creating new projects, building sites, and running the development server.

Commands:
- new: Scaffold a new Medusa project.
- build: Build the site into the output directory.
- serve: Run development server with live reload.
- md: Create a new markdown file interactively.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import click
import questionary

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
    from .build import BuildError, build_site

    try:
        result = build_site(project_root, include_drafts=drafts)
    except BuildError as exc:
        # Display user-friendly error message
        rel_path = exc.source_path.relative_to(project_root)
        click.echo(click.style("Build failed:", fg="red", bold=True), err=True)
        click.echo(click.style(f"  File: {rel_path}", fg="yellow"), err=True)
        click.echo(click.style(f"  Error: {exc.message}", fg="white"), err=True)
        raise SystemExit(1) from None
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


@cli.command()
def md():
    """Create a new markdown file interactively."""
    project_root = Path.cwd()
    site_dir = project_root / "site"

    if not site_dir.exists():
        raise click.ClickException(
            "No site/ directory found. Run this command from a Medusa project root."
        )

    # Find all valid content folders (exclude _ prefixed directories)
    folders = _get_content_folders(site_dir)
    if not folders:
        raise click.ClickException(
            "No content folders found in site/. Create a folder like site/posts/ first."
        )

    # Let user pick a folder
    folder = questionary.select(
        "Select folder:",
        choices=folders,
        style=_questionary_style(),
    ).ask()

    if folder is None:
        raise click.Abort()

    # Get filename from user
    name = questionary.text(
        "Filename (without .md extension):",
        validate=lambda x: len(x.strip()) > 0 or "Filename cannot be empty",
        style=_questionary_style(),
    ).ask()

    if name is None:
        raise click.Abort()

    name = name.strip()

    # Ask about date prefix
    add_date = questionary.confirm(
        "Prefix with today's date? (YYYY-MM-DD-)",
        default=True,
        style=_questionary_style(),
    ).ask()

    if add_date is None:
        raise click.Abort()

    # Build filename
    if add_date:
        date_prefix = datetime.now().strftime("%Y-%m-%d-")
        filename = f"{date_prefix}{name}.md"
    else:
        filename = f"{name}.md"

    # Check for duplicates
    if folder == ". (root)":
        target_dir = site_dir
    else:
        target_dir = site_dir / folder
    target_path = target_dir / filename

    if target_path.exists():
        raise click.ClickException(
            f"File already exists: {target_path.relative_to(project_root)}"
        )

    # Also check for slug collision (same name with different date)
    existing_slugs = _get_existing_slugs(target_dir)
    slug = _extract_slug(filename)
    if slug in existing_slugs:
        conflicting = [f for f in target_dir.iterdir() if _extract_slug(f.name) == slug]
        raise click.ClickException(
            f"A file with slug '{slug}' already exists: {conflicting[0].name}"
        )

    # Create the file with a basic template
    target_dir.mkdir(parents=True, exist_ok=True)
    title = _titleize(name)
    content = f"# {title}\n\n"
    target_path.write_text(content, encoding="utf-8")

    rel_path = target_path.relative_to(project_root)
    click.echo(f"Created {rel_path}")


def _get_content_folders(site_dir: Path) -> list[str]:
    """Get list of content folders in site directory.

    Returns folders that don't start with _ (excludes _layouts, _partials, etc.)
    """
    folders = []
    for path in site_dir.iterdir():
        if path.is_dir() and not path.name.startswith("_"):
            folders.append(path.name)
    # Sort alphabetically, then add root option at the beginning
    folders.sort()
    folders.insert(0, ". (root)")
    return folders


def _get_existing_slugs(folder: Path) -> set[str]:
    """Get set of existing slugs in a folder."""
    slugs = set()
    if folder.exists():
        for f in folder.iterdir():
            if f.is_file() and f.suffix == ".md":
                slugs.add(_extract_slug(f.name))
    return slugs


def _extract_slug(filename: str) -> str:
    """Extract slug from filename, removing date prefix and extension."""
    name = Path(filename).stem
    # Remove date prefix if present (YYYY-MM-DD-)
    parts = name.split("-")
    if len(parts) >= 4 and all(p.isdigit() for p in parts[:3]):
        name = "-".join(parts[3:])
    return name.lower()


def _titleize(name: str) -> str:
    """Convert filename to title case."""
    words = name.replace("-", " ").replace("_", " ").split()
    return " ".join(word.capitalize() for word in words)


def _questionary_style():
    """Return consistent questionary style."""
    return questionary.Style(
        [
            ("qmark", "fg:cyan bold"),
            ("question", "bold"),
            ("answer", "fg:cyan"),
            ("pointer", "fg:cyan bold"),
            ("highlighted", "fg:cyan bold"),
            ("selected", "fg:cyan"),
        ]
    )


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
            "@tailwindcss/aspect-ratio": "^0.4.2",
            "@tailwindcss/container-queries": "^0.1.1",
            "@tailwindcss/forms": "^0.5.9",
            "@tailwindcss/typography": "^0.5.15",
            "tailwindcss": "^3.4.13",
            "terser": "^5.36.0",
        },
    }
    (root / "package.json").write_text(
        json.dumps(package_json, indent=2) + "\n", encoding="utf-8"
    )

    _try_npm_install(root)
    _try_git_init(root)


def _try_git_init(root: Path) -> None:
    """Initialize a git repository if git is available."""
    if os.environ.get("MEDUSA_SKIP_GIT_INIT") == "1":
        return
    git_bin = shutil.which("git")
    if not git_bin:
        return
    try:
        subprocess.run(
            [git_bin, "init"],
            cwd=root,
            check=True,
            capture_output=True,
        )
    except Exception:
        # Non-fatal: user can run git init manually
        pass


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
            capture_output=True,
        )
    except Exception:
        # Non-fatal: user can run npm install manually
        pass
