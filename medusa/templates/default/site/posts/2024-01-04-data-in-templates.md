# Data in Templates

- `current_page`: Page object (see schema below)
- `pages`: PageCollection with helpers `group("posts")`, `with_tag("python")`, `drafts()`, `published()`, `sorted(reverse=True)`, `latest(count=5)`
- `tags`: TagCollection mapping tag name to PageCollection, e.g. `tags["python"].latest(3)`
- `data`: merged YAML from `data/`
- `url_for(path)`: builds URLs; respects `root_url`
- `js_path(name)`: returns `/assets/js/{name}.js`
- `css_path(name)`: returns `/assets/css/{name}.css`
- `img_path(name)`: returns `/assets/images/{name}.{ext}` (auto-detects png/jpg/jpeg/gif)
- `font_path(name)`: returns `/assets/fonts/{name}.{ext}` (auto-detects woff2/woff/ttf/otf)

### Collections API
- PageCollection (e.g., `pages`, `pages.group("posts")`):
  - `group(name)`, `with_tag(tag)`, `drafts()`, `published()`
  - `sorted(reverse=True)`, `latest(count=5)`
- TagCollection (e.g., `tags`):
  - Access tag pages via `tags["python"]`
  - Iterate: `{% for tag, tag_pages in tags.items() %}...{% endfor %}`

### Page Schema
```
Page:
  title: str
  body: str          # raw markdown/jinja
  content: str       # rendered HTML body
  description: str
  url: str           # "/posts/my-post/"
  slug: str
  date: datetime
  tags: list[str]
  draft: bool
  layout: str
  group: str         # first segment (e.g., "posts")
  path: Path
  folder: str
  filename: str
  source_type: str   # "markdown" or "jinja"
```
