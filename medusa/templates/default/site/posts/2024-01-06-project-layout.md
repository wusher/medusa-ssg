# Project Structure

Understanding how files are organized in a Medusa project.

## Directory Overview

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
├── assets/                  # Static assets
│   ├── css/main.css         # Tailwind entry point
│   ├── js/                  # JavaScript files
│   ├── images/              # Image files
│   └── fonts/               # Web fonts
├── data/                    # YAML data files
│   ├── site.yaml            # Site metadata
│   └── nav.yaml             # Navigation links
├── output/                  # Generated site (git-ignored)
├── medusa.yaml              # Configuration
├── tailwind.config.js       # Tailwind configuration
└── package.json             # Node dependencies
```

## The site/ Directory

This is where your content lives.

### Layouts

Files in `site/_layouts/` wrap your content. The `default.html.jinja` layout is used when no specific layout matches.

Layout resolution order:
1. Frontmatter `layout` field
2. Matching layout file (e.g., `about.md` → `_layouts/about.html.jinja`)
3. Group-based layout (e.g., posts → `_layouts/posts.html.jinja`)
4. Default layout (`_layouts/default.html.jinja`)

### Partials

Files in `site/_partials/` are reusable template fragments. Include them with:

```jinja
{% include "header.html.jinja" %}
```

### Content Files

Supported file types:

- **`.md`** - Markdown files (rendered to HTML)
- **`.html`** - Plain HTML (wrapped in layout)
- **`.jinja`** or **`.html.jinja`** - Jinja2 templates

### Drafts

Prefix files or folders with `_` to mark as draft:

- `site/posts/_work-in-progress.md`
- `site/_experiments/test.md`

## The assets/ Directory

Static files that get copied to output.

- `css/main.css` - Tailwind CSS entry point (processed automatically)
- `js/` - JavaScript files (optionally minified)
- `images/` - Image files (optionally optimized)
- `fonts/` - Web font files

## The data/ Directory

YAML files that become template variables:

- `site.yaml` - Merged into the root `data` object
- `{name}.yaml` - Available as `data.{name}`

## The output/ Directory

Generated static site. This directory is created by `medusa build` and should be git-ignored.

## Configuration

The `medusa.yaml` file configures your site:

```yaml
output_dir: output
root_url: https://example.com
port: 4000
ws_port: 4001
```

All settings are optional with sensible defaults.
