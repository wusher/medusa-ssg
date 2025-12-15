# Medusa: Technical Design Document

A minimal Python static site generator inspired by Bridgetown. No plugins. Convention over configuration.

## Goals

- Zero configuration for standard use cases
- Markdown content, no frontmatter required
- Jinja2 templating
- Tailwind CSS (built in, not optional)
- Fast dev server with hot reload
- Single command build and deploy

## Directory Convention

```
project/
├── site/
│   ├── _layouts/
│   │   └── default.html.jinja
│   ├── _partials/
│   │   ├── header.html.jinja
│   │   └── footer.html.jinja
│   ├── posts/
│   │   └── 2024-01-15-my-post.md
│   ├── about.md
│   ├── contact.md
│   └── index.md
├── data/
│   └── site.yaml
├── assets/
│   ├── css/
│   │   └── main.css          # Tailwind entry point
│   ├── js/
│   └── images/
├── output/                    # Generated site
└── medusa.yaml                # Optional overrides only
```

## Core Components

### 1. Content Processor

**File:** `medusa/content.py`

Responsibilities:
- Parse Markdown files with `mistune` (fast, extensible)
- Parse Jinja files as templates with dynamic content
- Extract all metadata from content and filesystem conventions
- Build list of Page objects

See **Page Schema** in Template Engine section for the full object structure.

URL derivation rules:
- `site/posts/2024-01-15-my-post.md` → `/posts/my-post/`
- `site/pages/about.md` → `/pages/about/`
- `site/about.md` → `/about/`
- `site/index.md` → `/`

### 2. Template Engine

**File:** `medusa/templates.py`

Jinja2 with these globals available in all templates:

| Variable | Description |
|----------|-------------|
| `data` | Data from `data/*.yaml` files merged together |
| `current_page` | Current page object |
| `pages` | List of all Page objects in the site |
| `tags` | Dict mapping tag names to list of Pages with that tag |
| `url_for(path)` | Generate URL for asset or page |

### Site Data

All YAML files in `data/` are loaded into the `data` object.

- `site.yaml` is special: its keys merge at the root level
- Other files: filename becomes the key

```
project/
  data/
    site.yaml       → data.title, data.url (merged at root)
    nav.yaml        → data.nav
    social.yaml     → data.social
```

**site.yaml** (merged at root)
```yaml
title: My Blog
url: https://example.com
author: Jane Doe
```

**nav.yaml**
```yaml
- label: Home
  url: /
- label: About
  url: /about/
- label: Posts
  url: /posts/
```

**social.yaml**
```yaml
twitter: https://twitter.com/jane
github: https://github.com/jane
```

**Usage in templates:**
```jinja
<title>{{ data.title }}</title>
<nav>
  {% for item in data.nav %}
    <a href="{{ item.url }}">{{ item.label }}</a>
  {% endfor %}
</nav>
<a href="{{ data.social.github }}">GitHub</a>
```

### Page Schema

```python
Page:
    # Content
    title: str              # "My Cool Post"
    body: str               # Raw markdown/jinja source
    content: str            # Rendered HTML content
    description: str        # First paragraph, max 160 chars
    
    # Routing
    url: str                # "/posts/my-post/"
    slug: str               # "my-post"
    
    # Metadata
    date: datetime          # 2024-01-15 00:00:00
    tags: list[str]         # ["python", "web/frontend"] (extracted from #hashtags in content)
    draft: bool             # False
    
    # Template
    layout: str             # "post"
    group: str              # "posts" (first segment of folder, or empty for root)
    
    # Filesystem
    path: Path              # site/posts/python/2024-01-15-my-post.md
    folder: str             # "posts/python" (relative to site/)
    filename: str           # "2024-01-15-my-post.md"
```

### Filtering Pages in Templates

```jinja
{# All published posts, newest first #}
{% for p in pages | selectattr('group', 'eq', 'posts') | rejectattr('draft') | sort(attribute='date', reverse=true) %}
  <a href="{{ p.url }}">{{ p.title }}</a>
{% endfor %}

{# All pages with a specific tag #}
{% for p in tags['python'] %}
  {{ p.title }}
{% endfor %}

{# List all tags with counts #}
{% for tag, tag_pages in tags.items() %}
  <a href="/tags/{{ tag }}/">{{ tag }}</a> ({{ tag_pages | length }})
{% endfor %}

{# Top 5 recent posts #}
{% for p in pages | selectattr('group', 'eq', 'posts') | sort(attribute='date', reverse=true) | batch(5) | first %}
  {{ p.title }}
{% endfor %}
```

Layout resolution:
1. Group convention (posts → `post.html.jinja`)
2. Fallback to `default.html.jinja`

Partials: `{% include "header.html.jinja" %}`

### 3. Asset Pipeline

**File:** `medusa/assets.py`

All assets copied to output:
- `assets/*` → `output/assets/*`

Tailwind processing:
- Input: `assets/css/main.css` with `@tailwind` directives
- Process via `tailwindcss` CLI (bundled or system)
- Output: minified CSS to `output/assets/css/main.css`
- Content paths scanned: `site/**/*.{html.jinja,md}`, `assets/**/*.js`

Image path rewriting:
- Relative src paths rewritten to `/assets/images/`
- `<img src="photo.png">` → `<img src="/assets/images/photo.png">`
- Markdown: `![alt](photo.png)` → `<img src="/assets/images/photo.png">`
- Subdirectories: `![logo](icons/logo.png)` → `/assets/images/icons/logo.png`
- Absolute URLs/paths unchanged

Other assets:
- JS: Minified via `rjsmin` or `terser`
- Images: Optional optimization via `pillow`

### 4. Build Orchestrator

**File:** `medusa/build.py`

Build sequence:
1. Clean `output/` directory
2. Load site data from `data/`
3. Discover and parse all content files into Page objects
4. Build `pages` list (available to all templates)
5. Render each Page through its layout
6. Process Tailwind CSS
7. Copy static assets
8. Generate sitemap.xml and RSS feed

Incremental builds (dev mode):
- Watch `site/` and `assets/` for changes
- Rebuild only affected files + dependents
- Full Tailwind rebuild on template changes (JIT requires it)

### 5. Dev Server

**File:** `medusa/server.py`

- Python `http.server` based, single threaded is fine
- WebSocket injection for live reload (use `websockets` library)
- File watcher via `watchdog`
- Serves from `output/` directory
- Injects reload script into HTML responses

## CLI Interface

```bash
medusa new mysite        # Scaffold new project
medusa serve             # Dev server on localhost:4000
medusa build             # Production build
medusa build --drafts    # Include draft posts
```

Implementation: `click` library

## Data Flow

```
[Markdown/Jinja Content]
        ↓
      Page
  (metadata from conventions)
        ↓
[Jinja2 Template + Layout]
        ↓
   [HTML Output]
        ↓
[Tailwind PostProcess]
        ↓
   [Final HTML]
```

## Configuration

`medusa.yaml` (all optional):

```yaml
url: https://mysite.com
title: My Site
output_dir: output
port: 4000

groups:
  posts:
    permalink: /blog/:slug/
```

Defaults are sane. Most sites need zero config.

## Dependencies

```
mistune              # Markdown to HTML
jinja2               # Templating
pyyaml               # Config and data files
click                # CLI
watchdog             # File watching
websockets           # Live reload
rjsmin               # JS minification
pillow               # Image optimization (optional)
```

Tailwind CSS: Require `tailwindcss` CLI installed via npm or standalone binary.

## File Processing Rules

| Source Pattern | Output | Notes |
|----------------|--------|-------|
| `*.md` | `*/index.html` | Pretty URLs |
| `*.html.jinja` in site | `*/index.html` | Jinja templates as pages |
| `_*` directories | Nothing | Underscore prefix = internal |
| `_*.md` or `_*.html.jinja` | Nothing | Underscore prefix = draft |
| `assets/*` | `assets/*` | Direct copy (CSS processed) |

## Convention Based Metadata

No frontmatter. All metadata derived from content and filesystem.

### Title
1. First `# H1` element in markdown
2. Titleized filename (`my-cool-post.md` → "My Cool Post")

### Date
1. Filename prefix (`2024-01-15-my-post.md` → 2024-01-15)
2. File modification time (fallback)

### Tags
Extracted from hashtags in content using pattern: `#[a-zA-Z][a-zA-Z0-9]{2,}(?:/[a-zA-Z0-9]+)*`

```markdown
This post is about #python and #web/frontend development.
```
→ `tags: ["python", "web/frontend"]`

Hashtags are stripped from rendered output. Hierarchical tags supported via `/`.

### Description
First paragraph of content, stripped to 160 characters.

### Layout
Group (first segment of folder) maps to layout file:
```
site/posts/*   → _layouts/post.html.jinja   (group: "posts")
site/docs/*    → _layouts/docs.html.jinja   (group: "docs")
site/*         → _layouts/default.html.jinja (group: "")
```

### Draft Status
Underscore prefix marks drafts:
```
site/posts/_work-in-progress.md             → draft: true
site/posts/2024-01-15-published.md          → draft: false
```

### Custom Layouts
Filename convention for non-default layouts:
```
site/contact[form].md                       → uses _layouts/form.html.jinja
site/posts/2024-01-15-announcement[hero].md → uses _layouts/hero.html.jinja
```

## Implementation Order

1. **Content parsing** (Page object, markdown, convention extraction)
2. **Template rendering** (Jinja2 setup, layout resolution)
3. **Static build** (full site generation)
4. **CLI** (build command)
5. **Dev server** (http server, file watching)
6. **Live reload** (websocket injection)
7. **Tailwind integration** (subprocess call to tailwindcss)
8. **Scaffolding** (new command with starter templates)

## What This Doesn't Do

- No frontmatter (conventions only)
- No plugin system
- No Ruby/Liquid compatibility
- No i18n
- No image CDN integration
- No CMS integration
- No SSR/ISR (static only)
- No component system beyond partials

## Performance Targets

- Cold build: < 1s for 100 pages
- Incremental rebuild: < 100ms
- Dev server startup: < 500ms

Use `concurrent.futures` for parallel content processing on larger sites.
