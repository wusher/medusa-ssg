# Asset Path Helpers

Medusa provides helper functions for referencing assets in templates.

## CSS Files

Use `css_path()` to reference stylesheets in `assets/css/`:

```jinja
<link rel="stylesheet" href="{{ css_path('main') }}">
<!-- Output: /assets/css/main.css -->
```

The `.css` extension is optional:

```jinja
{{ css_path('main') }}      {# main.css #}
{{ css_path('main.css') }}  {# also main.css #}
```

Subdirectories work too:

```jinja
{{ css_path('themes/dark') }}
<!-- Output: /assets/css/themes/dark.css -->
```

## JavaScript Files

Use `js_path()` to reference scripts in `assets/js/`:

```jinja
<script src="{{ js_path('app') }}"></script>
<!-- Output: /assets/js/app.js -->
```

Extension is optional:

```jinja
{{ js_path('app') }}     {# app.js #}
{{ js_path('app.js') }}  {# also app.js #}
```

## Images

Use `img_path()` to reference images in `assets/images/`:

```jinja
<img src="{{ img_path('logo.png') }}" alt="Logo">
<!-- Output: /assets/images/logo.png -->
```

### Auto-Detection

Omit the extension and Medusa finds the file:

```jinja
{{ img_path('logo') }}
```

Searches for: `.png`, `.jpg`, `.jpeg`, `.gif`, `.svg`, `.webp`

## Fonts

Use `font_path()` to reference fonts in `assets/fonts/`:

```jinja
@font-face {
  font-family: 'Inter';
  src: url('{{ font_path('inter.woff2') }}') format('woff2');
}
```

### Auto-Detection

Omit the extension:

```jinja
{{ font_path('inter') }}
```

Searches for: `.woff2`, `.woff`, `.ttf`, `.otf`

## URL Helper

Use `url_for()` to generate URLs that respect `root_url`:

```jinja
<a href="{{ url_for('/about/') }}">About</a>
```

## With root_url

All helpers respect the `root_url` setting in `medusa.yaml`:

```yaml
root_url: https://cdn.example.com
```

Then:

```jinja
{{ css_path('main') }}
<!-- Output: https://cdn.example.com/assets/css/main.css -->
```

## Code Highlighting CSS

Generate Pygments CSS for syntax highlighting:

```jinja
{# Inline styles #}
<style>{{ pygments_css() }}</style>

{# Or link to a CSS file you've created #}
<link rel="stylesheet" href="{{ css_path('pygments') }}">
```

## Complete Example

A typical layout head section:

```jinja
<head>
  <meta charset="UTF-8">
  <title>{{ current_page.title }} | {{ data.title }}</title>

  <link rel="stylesheet" href="{{ css_path('main') }}">
  <style>{{ pygments_css() }}</style>

  <link rel="icon" href="{{ img_path('favicon') }}">

  <script src="{{ js_path('app') }}" defer></script>
</head>
```
