# medusa-ssg

Minimal Python static site generator. Markdown + Jinja2, Tailwind CSS built-in, zero configuration, optional frontmatter.

## Quick Start

```bash
pip install medusa-ssg
medusa new mysite
cd mysite
medusa serve
```

Open http://localhost:4000 to see your site with live reload.

## Features

- **Zero frontmatter required** — title, date, tags, and description derived from filenames and content
- **Optional YAML frontmatter** — add custom metadata when you need it
- **Markdown + Jinja2** — write content in Markdown, layouts in Jinja2
- **Tailwind CSS** — built-in pipeline with automatic processing
- **Live reload** — dev server with WebSocket-based hot reload
- **Pretty URLs** — `/posts/hello/` not `/posts/hello.html`
- **Automatic sitemap & RSS** — generated on build
- **Custom 404 pages** — static HTML served with proper status codes
- **Syntax highlighting** — Pygments-powered code blocks
- **Table of contents** — auto-generated from headings

## Requirements

- Python 3.10+
- Node.js 16+ (for Tailwind CSS)

## Installation

```bash
# Install Medusa
pip install medusa-ssg

# Or install from source
git clone https://github.com/yourname/medusa.git
cd medusa
pip install -e .
```

## CLI Commands

```bash
medusa new NAME          # Create a new project
medusa build             # Build site to output/
medusa build --drafts    # Include draft content
medusa serve             # Dev server at localhost:4000
medusa serve --port 3000 # Custom port
medusa serve --drafts    # Include drafts in dev
medusa md                # Interactive markdown file creator
medusa --version         # Show version
```

## Project Structure

```
mysite/
├── site/                    # Content and templates
│   ├── _layouts/            # Page layouts
│   │   └── default.html.jinja
│   ├── _partials/           # Reusable components
│   │   ├── header.html.jinja
│   │   └── footer.html.jinja
│   ├── posts/               # Blog posts
│   │   └── 2024-01-15-hello-world.md
│   ├── index.jinja          # Home page
│   ├── about.md             # Static page
│   └── 404.html             # Custom error page
├── assets/
│   ├── css/main.css         # Tailwind entry point
│   ├── js/main.js
│   └── images/
├── data/                    # YAML data files
│   ├── site.yaml            # Site metadata
│   └── nav.yaml             # Navigation links
├── output/                  # Generated site (git-ignored)
├── medusa.yaml              # Configuration
├── tailwind.config.js
└── package.json
```

## Configuration

Create `medusa.yaml` in your project root:

```yaml
# Output directory (default: output)
output_dir: output

# Base URL used to absolutize all links in output (default: empty).
# medusa serve always uses http://localhost:<port> for dev builds.
root_url: https://example.com

# Dev server port (default: 4000)
port: 4000

# WebSocket port for live reload (default: port + 1)
ws_port: 4001
```

## Writing Content

### Supported File Types

Medusa processes these file types in the `site/` directory:

- **Markdown** (`.md`) — Content files with full Markdown support
- **HTML** (`.html`) — Plain HTML files, processed as pages with pretty URLs
- **Jinja templates** (`.html.jinja`, `.jinja`) — Templates with Jinja2 syntax

All other file types are ignored.

### Markdown Pages

Create `.md` files anywhere in `site/`:

```markdown
# My Page Title

Content goes here. The first `# heading` becomes the page title.

Use #hashtags for tags. #python #tutorial
```

### Dated Posts

Name files with a date prefix for automatic date extraction:

```
site/posts/2024-01-15-my-post.md  →  /posts/my-post/
site/posts/2024-02-20-another.md  →  /posts/another/
```

### Drafts

Prefix files or folders with `_` to mark as draft:

```
site/posts/_work-in-progress.md   # Draft post
site/_experiments/test.md          # Draft folder
```

Drafts are excluded from builds unless you use `--drafts`.

### Frontmatter

Add optional YAML frontmatter for custom metadata:

```markdown
---
author: Jane Doe
featured: true
category: tutorials
---

# My Post Title

Content goes here.
```

Access frontmatter in templates with `{{ frontmatter.author }}`.

## Templates

### Available Variables

| Variable | Description |
|----------|-------------|
| `current_page` | The current page object |
| `pages` | Collection of all pages |
| `tags` | Map of tag names to page collections |
| `data` | Merged YAML from `data/` directory |
| `frontmatter` | Current page's YAML frontmatter |
| `url_for(path)` | Generate URLs with base path |
| `render_toc(page)` | Generate nested `<ul>` table of contents |
| `css_path(name)` | Path to CSS file in `assets/css/` |
| `js_path(name)` | Path to JS file in `assets/js/` |
| `img_path(name)` | Path to image in `assets/images/` (auto-detects extension) |
| `font_path(name)` | Path to font in `assets/fonts/` (auto-detects extension) |
| `pygments_css()` | CSS for syntax highlighting |

### Page Object

```python
current_page.title        # Page title
current_page.content      # Rendered HTML
current_page.body         # Raw markdown/source text
current_page.description  # First paragraph (for SEO)
current_page.excerpt      # Full first paragraph
current_page.url          # URL path (/posts/hello/)
current_page.slug         # URL slug (hello)
current_page.date         # Publication date
current_page.tags         # List of tags
current_page.toc          # List of headings for TOC
current_page.draft        # Is draft?
current_page.layout       # Layout name
current_page.group        # Folder group (posts, pages, etc.)
current_page.frontmatter  # YAML frontmatter dict
```

### Collections API

```jinja
{# Get posts #}
{% for post in pages.group("posts").sorted() %}
  <a href="{{ post.url }}">{{ post.title }}</a>
{% endfor %}

{# Filter by tag #}
{% for post in pages.with_tag("python").latest(5) %}
  {{ post.title }}
{% endfor %}

{# Published only (excludes drafts) #}
{% for page in pages.published() %}
  {{ page.title }}
{% endfor %}
```

### Sorting

Pages are sorted by three criteria in order:

1. **Date** — Newest first (from filename or file modification time)
2. **Number prefix** — If dates are equal, by number prefix in filename
3. **Filename** — If dates and numbers are equal, alphabetically

Examples of number prefixes:
```
site/docs/01-introduction.md   →  Sorted first
site/docs/02-getting-started.md →  Sorted second
site/docs/03-advanced.md       →  Sorted third
```

You can also combine date and number prefixes:
```
site/posts/2024-01-15-01-part-one.md
site/posts/2024-01-15-02-part-two.md
```

### Partials

```jinja
{# site/_partials/card.html.jinja #}
<div class="card">
  <h3>{{ title }}</h3>
  <p>{{ description }}</p>
</div>

{# Include in any template #}
{% include "card.html.jinja" %}
```

## Data Files

YAML files in `data/` are available in templates:

```yaml
# data/site.yaml - merged into data root
title: My Site
author: Jane Doe

# data/social.yaml - available as data.social
- platform: GitHub
  url: https://github.com/username
- platform: Twitter
  url: https://twitter.com/username
```

```jinja
<h1>{{ data.title }}</h1>
<p>By {{ data.author }}</p>

{% for link in data.social %}
  <a href="{{ link.url }}">{{ link.platform }}</a>
{% endfor %}
```

## Static Files

### HTML Pages

HTML files (`.html`) in `site/` are processed as pages with pretty URLs. For example:
- `site/about.html` → `/about/`
- `site/404.html` → `/404/`

The content is wrapped in your layout template like Markdown pages.

### 404 Page

Create `site/404.html` for a custom error page. It will be processed as a page at `/404/` and served with a 404 status code by the dev server.

## Asset Helpers

Reference assets in your templates:

```jinja
<link rel="stylesheet" href="{{ css_path('main') }}">
<script src="{{ js_path('app') }}"></script>
<img src="{{ img_path('logo') }}" alt="Logo">
```

All helpers respect `root_url` for CDN support. Image and font helpers auto-detect file extensions when omitted.

## Syntax Highlighting

Code blocks with language identifiers get Pygments highlighting:

````markdown
```python
def hello():
    print("Hello!")
```
````

Include the CSS in your layout:

```jinja
<style>{{ pygments_css() }}</style>
```

## Deployment

### Netlify

Create `netlify.toml`:

```toml
[build]
  command = "pip install -e . && medusa build"
  publish = "output"

[[redirects]]
  from = "/*"
  to = "/404.html"
  status = 404
```

### Vercel

Create `vercel.json`:

```json
{
  "buildCommand": "pip install -e . && medusa build",
  "outputDirectory": "output"
}
```

### GitHub Pages

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: pip install medusa-ssg
      - run: npm install
      - run: medusa build
      - uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./output
```

### Manual / Any Host

```bash
medusa build
# Upload contents of output/ to your server
```

## Development

```bash
# Clone and install
git clone https://github.com/yourname/medusa.git
cd medusa
make dev  # Installs dependencies and configures pre-commit hook

# Run tests
pytest

# Run with coverage
pytest --cov=medusa --cov-report=term-missing
```

## License

MIT License. See [LICENSE](LICENSE) for details.
