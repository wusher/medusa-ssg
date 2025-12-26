# Development Server

Medusa includes a powerful dev server for local development.

## Starting the Server

Run the development server:

```bash
medusa serve
```

Your site is available at http://localhost:4000

## Live Reload

The server automatically reloads your browser when files change. It watches:

- `site/` - Content and templates
- `assets/` - CSS, JS, and images
- `data/` - YAML data files
- `medusa.yaml` - Configuration
- `tailwind.config.js` - Tailwind configuration

Changes are detected instantly and the browser refreshes automatically.

## Including Drafts

View draft content while developing:

```bash
medusa serve --drafts
```

Draft files (prefixed with `_`) will be included in the build.

## Custom Ports

Change the HTTP port:

```bash
medusa serve --port 3000
```

The WebSocket port (for live reload) defaults to HTTP port + 1. Override it:

```bash
medusa serve --port 3000 --ws-port 3001
```

## Custom 404 Page

Create `site/404.html` or `site/404.md` for a custom error page. The dev server displays it with the correct 404 status code.

## How It Works

The dev server uses:

1. **ThreadingHTTPServer** for handling requests
2. **WebSocket connection** for live reload
3. **File watching** with debouncing to prevent rapid rebuilds
4. **Atomic directory swaps** for consistent output

## Contributing to Medusa

If you're working on Medusa itself:

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests with coverage
make test

# Run linting
make lint

# Run both before committing
make lint test
```

Medusa requires 100% test coverage. Run individual tests with:

```bash
python -m pytest tests/test_content.py::test_function_name -v
```
