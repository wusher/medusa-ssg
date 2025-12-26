# Simplification Roadmap

Goal: Remove complexity. Less code = less bugs = easier to understand.

## What to Remove

### 1. Remove `site/` subdirectory requirement

**Current:** Content must be in `site/` folder
**Change:** Content at project root. Less nesting.

```
# Before
mysite/site/posts/hello.md

# After
mysite/posts/hello.md
```

### 2. Remove `data/` folder and multiple YAML files

**Current:** `data/site.yaml`, `data/nav.yaml`, etc.
**Change:** Single `_config.yml` at root (like Jekyll)

### 3. Remove `[layout]` filename syntax

**Current:** `about[hero].md` → uses hero layout
**Change:** Use frontmatter only. One way to do things.

### 4. Remove hashtag extraction from content

**Current:** `#python` in content becomes a tag and gets stripped
**Change:** Tags only via frontmatter. Hashtags are just text.

This removes:
- `extract_tags()` function
- `strip_hashtags()` function
- `HASHTAG_RE` regex

### 5. Remove complex layout resolution cascade

**Current:** Checks `folder/name` → `folder` → `name` → `default`
**Change:** Check `folder` → `default`. That's it.

### 6. Remove `.jinja` file processing as pages

**Current:** `.jinja` and `.html.jinja` files become pages
**Change:** Only `.md` files become pages. Templates are only in `_layouts/`.

### 7. Remove TOC extraction

**Current:** Builds table of contents from headings
**Change:** Remove. Users can add their own TOC if needed.

### 8. Remove excerpt extraction

**Current:** Extracts first paragraph as excerpt
**Change:** Use `description` from first paragraph only. Simpler.

### 9. Remove frontmatter support

**Current:** YAML frontmatter parsed and stored
**Change:** Remove. All metadata from filename and content conventions.

Or keep frontmatter but only for `layout` override. Nothing else.

### 10. Remove image path rewriting

**Current:** Rewrites `![](image.png)` to `/assets/images/...`
**Change:** Users write correct paths. Less magic.

### 11. Remove `_partials/` folder

**Current:** Separate folder for includes
**Change:** Use `_includes/` like Jekyll, or just put includes in `_layouts/`.

### 12. Remove WebSocket live reload complexity

**Current:** Custom WebSocket server for live reload
**Change:** Simple polling or browser-sync. Less code to maintain.

### 13. Remove Tailwind/asset pipeline

**Current:** Processes CSS through Tailwind, minifies JS
**Change:** Just copy files. Users handle their own CSS build if needed.

### 14. Remove root_url absolutization

**Current:** Rewrites all URLs to absolute when root_url set
**Change:** Users write correct URLs. Or only do it for RSS/sitemap.

## What to Keep

- Markdown → HTML conversion (core purpose)
- Date extraction from filenames (convention)
- Draft support with `_` prefix (convention)
- Pretty URLs (convention)
- RSS and sitemap generation (expected feature)
- Syntax highlighting in code blocks (expected feature)
- Single layout template wrapping (minimal templating)

## Simplified Architecture

```
_config.yml          # Site config (title, url)
_layouts/
  default.html       # One layout file
posts/
  2024-01-15-hello.md
about.md
index.md
output/              # Generated
```

That's the entire project structure. Nothing else needed.

## Code Reduction Targets

| Module | Current LOC | Target | Remove |
|--------|-------------|--------|--------|
| utils.py | ~230 | ~100 | hashtag regex, complex helpers |
| content.py | ~500 | ~200 | TOC, excerpt, frontmatter complexity |
| build.py | ~240 | ~150 | asset pipeline integration |
| collections.py | ~80 | ~40 | simplify sorting |
| templates.py | ~130 | ~80 | remove partials, simplify |
| assets.py | ~80 | 0 | remove entirely |
| server.py | ~180 | ~100 | simplify live reload |

**Total: ~1400 LOC → ~670 LOC (52% reduction)**

## Implementation Order

1. Remove hashtag extraction (quick win, cleaner code)
2. Remove `[layout]` filename syntax
3. Simplify layout resolution
4. Remove `.jinja` as page source type
5. Remove `site/` subdirectory requirement
6. Remove `data/` folder, use single config
7. Remove asset pipeline
8. Simplify live reload

## Principle

Every feature removed is:
- Less code to maintain
- Less documentation to write
- Less for users to learn
- Fewer edge cases
- Fewer bugs

If a feature isn't essential for "markdown → blog", remove it.
