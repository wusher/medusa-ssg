# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Test Commands

```bash
make lint test     # Run before committing (required to pass)
make lint          # Run ruff check and format
make test          # Run pytest with 100% coverage requirement
make dev           # Install with dev dependencies
python -m pytest tests/test_content.py::test_html_file_processing -v  # Run single test
```

## Architecture Overview

Medusa is a minimal static site generator that processes Markdown, HTML, and Jinja2 files into a static website.

### Core Pipeline

1. **CLI** (`cli.py`) - Entry point. Commands: `new`, `build`, `serve`, `md`
2. **Build** (`build.py`) - Orchestrates the build: loads config/data, processes content, renders templates, writes output
3. **Content** (`content.py`) - `ContentProcessor` loads source files, extracts metadata (date from filename, tags from #hashtags, title from first `#` heading, excerpt from first paragraph, TOC from headings), renders Markdown via mistune
4. **Templates** (`templates.py`) - `TemplateEngine` wraps Jinja2, provides globals (`pages`, `tags`, `data`, `url_for`, `render_toc`)
5. **Collections** (`collections.py`) - `PageCollection` and `TagCollection` for template querying (`.group()`, `.with_tag()`, `.published()`, `.sorted()`)
6. **Assets** (`assets.py`) - Copies assets, runs Tailwind CSS, minifies JS
7. **Server** (`server.py`) - Dev server with WebSocket live reload

### Key Data Flow

```
site/*.md,html,jinja → ContentProcessor.load() → List[Page]
                                                     ↓
                       TemplateEngine.render_page() ← Layout + Page
                                                     ↓
                       output/{url}/index.html ← Rendered HTML
```

### File Processing Rules

Only these file types in `site/` are processed:
- `.md` - Markdown (rendered to HTML, title from `#` heading, tags from `#hashtags`)
- `.html` - Plain HTML (wrapped in layout, pretty URLs)
- `.html.jinja`, `.jinja` - Jinja2 templates

Files/folders prefixed with `_` are:
- `_layouts/`, `_partials/` - Template directories
- `_*.md` - Drafts (excluded unless `--drafts` flag)

### Page Sorting

`PageCollection.sorted()` orders by: **date** (newest first) → **number prefix** (e.g., `01-intro.md`) → **filename** alphabetically

### Layout Resolution

Searches `_layouts/` in order: `{folder}/{name}` → `{group}` → `default`, trying extensions `.html.jinja`, `.jinja`, `.html`

## Configuration

`medusa.yaml` options: `output_dir` (default: "output"), `root_url` (base URL for absolutizing links), `port` (dev server, default: 4000), `ws_port` (live reload WebSocket)

## Template Globals

Available in all templates:
- `current_page` - Current Page object (title, content, body, url, date, tags, toc, excerpt, description, frontmatter)
- `pages` - PageCollection with `.group()`, `.with_tag()`, `.published()`, `.drafts()`, `.sorted()`, `.latest(n)`
- `tags` - TagCollection mapping tag names to PageCollection
- `data` - Merged YAML from `data/*.yaml` (site.yaml merges to root)
- `frontmatter` - Current page's YAML frontmatter dict
- `url_for(path)` - Generates URLs with root_url prefix
- `render_toc(page)` - Generates nested `<ul>` from page headings
- `css_path()`, `js_path()`, `img_path()`, `font_path()` - Asset URL helpers
- `pygments_css()` - CSS for syntax highlighting
