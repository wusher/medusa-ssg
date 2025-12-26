# Simplification Roadmap

Goal: Make Medusa the simplest way to turn markdown files into a blog. Convention over configuration.

## Guiding Principles

1. **Zero config by default** — Everything works out of the box
2. **Just add markdown** — Drop files in a folder, get a blog
3. **Sensible defaults** — Built-in layout, styles, RSS, sitemap
4. **Progressive disclosure** — Simple things simple, complex things possible

## High Priority Changes

### 1. Built-in Default Layout

**Current:** Users must create `_layouts/default.html.jinja`

**Proposed:** Ship a built-in default layout. Users only create `_layouts/` if they want to customize.

```
# Just works - no _layouts folder needed
site/
  posts/
    2024-01-15-hello.md
  index.md
```

Jekyll does this with themes. We should have a sensible HTML5 layout built-in.

### 2. Flatten Project Structure

**Current:**
```
mysite/
  site/           # Content here
  assets/         # CSS/JS here
  data/           # YAML here
  medusa.yaml     # Config
```

**Proposed:**
```
mysite/
  _posts/         # Blog posts (dated)
  _pages/         # Static pages
  _layouts/       # Optional overrides
  index.md        # Home page
```

Like Jekyll, content at the root. Underscore folders are special. Everything else is content.

### 3. Auto-generate Index Pages

**Current:** Users must create `index.md` for each folder

**Proposed:** Auto-generate index pages listing folder contents.

```
site/posts/           →  /posts/ shows list of all posts
site/docs/            →  /docs/ shows list of all docs
```

User can override by creating their own `index.md`.

### 4. Built-in CSS

**Current:** Requires Tailwind + Node.js setup

**Proposed:** Ship minimal, beautiful CSS by default. No build step.

Options:
- Embed [Simple.css](https://simplecss.org/) or [Water.css](https://watercss.kognise.dev/)
- Or create our own minimal stylesheet
- Users can override with custom CSS file

### 5. Remove Jinja Template Requirement

**Current:** Layouts use Jinja2 syntax

**Proposed:** Support simple variable substitution for basic use:

```html
<!-- _layouts/default.html -->
<html>
<head><title>{{ title }}</title></head>
<body>
  {{ content }}
</body>
</html>
```

Keep Jinja for advanced users, but simple `{{ var }}` works without learning Jinja.

## Medium Priority Changes

### 6. Simplify Layout Resolution

**Current:** Complex cascade: `folder/name` → `folder` → `name` → `default`

**Proposed:** Simple rules:
1. Frontmatter `layout:` if specified
2. Folder name (e.g., `_posts/` uses `post` layout)
3. `default`

### 7. Remove `[layout]` Filename Syntax

**Current:** `about[hero].md` uses `hero` layout

**Proposed:** Use frontmatter only:
```yaml
---
layout: hero
---
```

Simpler mental model. One way to do things.

### 8. Simplify Tag System

**Current:** `#hashtags` extracted from content, stripped on render

**Proposed:** Optional frontmatter only:
```yaml
---
tags: [python, tutorial]
---
```

Hashtags in content are just text. Simpler, more predictable.

### 9. Single Config File

**Current:** `medusa.yaml` + `data/*.yaml` files

**Proposed:** Single `_config.yml` (Jekyll-style):
```yaml
title: My Blog
author: Jane Doe
url: https://example.com

# Everything in one place
nav:
  - Home: /
  - About: /about/
```

### 10. Automatic Pagination

Add pagination for post listings:
```jinja
{% for post in posts | paginate(10) %}
```

Generates `/posts/`, `/posts/page/2/`, etc.

## Lower Priority / Future

### 11. Built-in Themes

Ship 2-3 themes users can choose:
```yaml
theme: minimal  # or: blog, docs
```

### 12. Draft Preview URL

Drafts accessible at `/_drafts/post-name/` in dev server without `--drafts` flag.

### 13. Image Optimization

Auto-optimize images in `assets/images/` during build. No config needed.

### 14. Markdown Extensions

Built-in support for:
- Tables (already have via mistune)
- Footnotes (already have)
- Task lists `- [ ]`
- Auto-linking URLs

### 15. Remove Dev Server Complexity

Simplify live reload. Consider using `watchdog` + simple HTTP server instead of custom WebSocket implementation.

## What NOT to Remove

Keep these features - they "just work" and users expect them:

- **RSS feed** — Auto-generated, zero config
- **Sitemap** — Auto-generated, zero config
- **Syntax highlighting** — Works automatically for code blocks
- **Pretty URLs** — `/posts/hello/` not `/posts/hello.html`
- **Date extraction** — `2024-01-15-title.md` just works
- **Drafts** — `_` prefix, simple convention

## Migration Path

1. Keep backward compatibility
2. New `medusa init` creates simplified structure
3. Existing projects continue working
4. Deprecation warnings for old patterns

## Comparison: Current vs Proposed

### Current (Complex)
```
mysite/
├── site/
│   ├── _layouts/
│   │   └── default.html.jinja    # Required
│   ├── _partials/
│   ├── posts/
│   │   └── 2024-01-15-hello.md
│   └── index.md
├── assets/
│   ├── css/main.css
│   └── js/main.js
├── data/
│   └── site.yaml
├── medusa.yaml
├── tailwind.config.js            # Requires Node.js
└── package.json
```

### Proposed (Simple)
```
mysite/
├── _posts/
│   └── 2024-01-15-hello.md
├── about.md
└── index.md
```

That's it. Everything else is optional and has sensible defaults.

## Implementation Order

1. Built-in default layout (unblocks everything else)
2. Flatten project structure
3. Built-in CSS
4. Auto-generate index pages
5. Simplify config to single file
6. Remove Node.js/Tailwind requirement
7. Add themes

## References

- [Jekyll](https://jekyllrb.com/) — The gold standard for simplicity
- [Hugo](https://gohugo.io/) — Fast, good defaults
- [Eleventy](https://www.11ty.dev/) — Flexible but simple
- [Zola](https://www.getzola.org/) — Single binary, no deps
- [Bear Blog](https://bearblog.dev/) — Extreme minimalism
