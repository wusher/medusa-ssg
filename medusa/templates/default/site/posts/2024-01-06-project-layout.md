# Project Layout

```
site/
  _layouts/ default.html.jinja
  _partials/ header.html.jinja, footer.html.jinja
  posts/ 2024-01-15-my-post.md
  index.md, about.md
assets/
  css/main.css  # Tailwind entry
  js/
  images/
data/
  site.yaml, nav.yaml, ...
output/           # build output (generated)
medusa.yaml       # optional overrides
```
