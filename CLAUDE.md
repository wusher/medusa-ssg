# Claude Code Guidelines

## Before Committing

Always run and ensure these pass before committing changes:

```bash
make lint test
```

- `make lint` runs ruff to check and fix code style
- `make test` runs pytest with 100% code coverage requirement

## Project Structure

- `medusa/` - Main package source code
- `tests/` - Test files (100% coverage required)
- `site/` - Content directory for static sites

## File Processing

Only these file types are processed in `site/`:
- `.md` - Markdown files
- `.html` - HTML files (processed as pages with pretty URLs)
- `.html.jinja`, `.jinja` - Jinja2 templates

## Sorting

Pages are sorted by: date (newest first) → number prefix → filename
