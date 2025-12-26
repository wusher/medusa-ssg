# Template Variables

Medusa makes your content available through several template variables.

## Current Page

Access the current page's properties with `current_page`:

```jinja
<h1>{{ current_page.title }}</h1>
<time>{{ current_page.date.strftime('%B %d, %Y') }}</time>
<div>{{ current_page.content | safe }}</div>
```

### Page Properties

| Property | Description |
|----------|-------------|
| `title` | Page title from first heading |
| `content` | Rendered HTML content |
| `body` | Raw markdown/source text |
| `description` | First paragraph (for SEO) |
| `excerpt` | Full first paragraph |
| `url` | URL path like `/posts/hello/` |
| `slug` | URL slug like `hello` |
| `date` | Publication datetime |
| `tags` | List of hashtag tags |
| `draft` | Boolean draft status |
| `layout` | Layout template name |
| `group` | Content group (e.g., `posts`) |
| `toc` | List of headings for TOC |
| `frontmatter` | YAML frontmatter dict |

## Pages Collection

Query all pages with the `pages` collection:

```jinja
{% for post in pages.group("posts").sorted() %}
  <a href="{{ post.url }}">{{ post.title }}</a>
{% endfor %}
```

### Collection Methods

- `.group("posts")` - Filter by content folder
- `.with_tag("python")` - Filter by tag
- `.published()` - Exclude drafts
- `.drafts()` - Only drafts
- `.sorted()` - Sort by date, then number prefix, then filename
- `.latest(5)` - Get the 5 most recent pages

Chain methods together:

```jinja
{% for post in pages.group("posts").with_tag("python").latest(3) %}
  {{ post.title }}
{% endfor %}
```

## Tags Collection

Access pages by tag with `tags`:

```jinja
{% for tag, tag_pages in tags.items() %}
  <h2>{{ tag }}</h2>
  {% for page in tag_pages.latest(5) %}
    <a href="{{ page.url }}">{{ page.title }}</a>
  {% endfor %}
{% endfor %}
```

Or get pages for a specific tag:

```jinja
{% for page in tags["python"].sorted() %}
  {{ page.title }}
{% endfor %}
```

## Data Files

YAML files in `data/` are available as `data`:

```jinja
<h1>{{ data.title }}</h1>
<p>{{ data.description }}</p>

{% for link in data.social %}
  <a href="{{ link.url }}">{{ link.platform }}</a>
{% endfor %}
```

## Frontmatter

Access the current page's frontmatter:

```jinja
{% if frontmatter.featured %}
  <span class="badge">Featured</span>
{% endif %}

<p>By {{ frontmatter.author }}</p>
```

## URL Helper

Generate URLs that respect `root_url`:

```jinja
<a href="{{ url_for('/about/') }}">About</a>
```

## Table of Contents

Render a nested list of headings:

```jinja
<nav class="toc">
  {{ render_toc(current_page) }}
</nav>
```
