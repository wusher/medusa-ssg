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


@click.group()
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
def serve(drafts: bool):
    """Run dev server with live reload."""
    project_root = Path.cwd()
    from .server import DevServer

    server = DevServer(project_root)
    server.start(include_drafts=drafts)


def main():
    """Entry point for the CLI application."""


def _scaffold(root: Path) -> None:
    """Create the directory structure and files for a new Medusa project.

    Args:
        root: Root directory for the new project.
    """
    (root / "site" / "_layouts").mkdir(parents=True, exist_ok=True)
    (root / "site" / "_partials").mkdir(parents=True, exist_ok=True)
    (root / "site" / "posts").mkdir(parents=True, exist_ok=True)
    (root / "assets" / "css").mkdir(parents=True, exist_ok=True)
    (root / "assets" / "js").mkdir(parents=True, exist_ok=True)
    (root / "assets" / "images").mkdir(parents=True, exist_ok=True)
    (root / "data").mkdir(parents=True, exist_ok=True)

    (root / "medusa.yaml").write_text(
        "output_dir: output\nport: 4000\n", encoding="utf-8"
    )

    (root / "data" / "site.yaml").write_text(
        "title: My Medusa Site\nurl: https://example.com\nauthor: Jane Doe\n",
        encoding="utf-8",
    )
    (root / "data" / "nav.yaml").write_text(
        "- label: Home\n  url: /\n- label: About\n  url: /about/\n- label: Posts\n  url: /posts/\n",
        encoding="utf-8",
    )

    (root / "assets" / "css" / "main.css").write_text(
        "@tailwind base;\n@tailwind components;\n@tailwind utilities;\n\nbody { @apply bg-gray-50 text-gray-900; }\n",
        encoding="utf-8",
    )
    (root / "assets" / "js" / "main.js").write_text(
        "console.log('Medusa ready');\n", encoding="utf-8"
    )

    (root / "site" / "_layouts" / "default.html.jinja").write_text(
        """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ current_page.title }} | {{ data.title }}</title>
  <link rel="stylesheet" href="{{ url_for('/assets/css/main.css') }}">
</head>
<body class="min-h-screen flex flex-col">
  {% include "header.html.jinja" %}
  <main class="container mx-auto px-6 py-10 flex-1">
    {{ page_content | safe }}
  </main>
  {% include "footer.html.jinja" %}
</body>
</html>
""",
        encoding="utf-8",
    )

    (root / "site" / "_partials" / "header.html.jinja").write_text(
        """<header class="border-b border-gray-200 bg-white">
  <div class="container mx-auto px-6 py-4 flex items-center justify-between">
    <a href="/" class="text-lg font-semibold">{{ data.title }}</a>
    <nav class="space-x-4 text-sm">
      {% for item in data.nav %}
        <a href="{{ item.url }}" class="text-gray-700 hover:text-black">{{ item.label }}</a>
      {% endfor %}
    </nav>
  </div>
</header>
""",
        encoding="utf-8",
    )

    (root / "site" / "_partials" / "footer.html.jinja").write_text(
        """<footer class="border-t border-gray-200 bg-white">
  <div class="container mx-auto px-6 py-6 text-sm text-gray-600">
    © {{ data.title }} — Built with Medusa.
  </div>
</footer>
""",
        encoding="utf-8",
    )

    (root / "site" / "index.md").write_text(
        """# Welcome to Medusa

This is your brand new site. Edit `site/index.md` to get started.

Check out the #posts for updates and follow along.
""",
        encoding="utf-8",
    )

    (root / "site" / "about.md").write_text(
        """# About

Medusa is a minimal static site generator using Markdown and Jinja2.
""",
        encoding="utf-8",
    )

    (root / "site" / "posts" / "2024-01-15-my-post.md").write_text(
        """# First Post

This is your first post powered by Medusa. Add more markdown files in `site/posts/`.

Happy #writing!
""",
        encoding="utf-8",
    )
