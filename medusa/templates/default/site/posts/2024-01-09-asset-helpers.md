# Asset Path Helpers

Medusa provides convenient helper functions for referencing assets in your templates.

## CSS Files

Use `css_path()` to reference stylesheets in `assets/css/`:

```jinja
<link rel="stylesheet" href="{{ css_path('main') }}">
<!-- outputs: /assets/css/main.css -->

<link rel="stylesheet" href="{{ css_path('themes/dark') }}">
<!-- outputs: /assets/css/themes/dark.css -->
```

## JavaScript Files

Use `js_path()` to reference scripts in `assets/js/`:

```jinja
<script src="{{ js_path('main') }}"></script>
<!-- outputs: /assets/js/main.js -->

<script src="{{ js_path('vendor/alpine') }}"></script>
<!-- outputs: /assets/js/vendor/alpine.js -->
```

## Images

Use `img_path()` to reference images in `assets/images/`. The helper automatically detects the file extension by searching for `.png`, `.jpg`, `.jpeg`, then `.gif`:

```jinja
<img src="{{ img_path('logo') }}" alt="Logo">
<!-- finds logo.png, logo.jpg, logo.jpeg, or logo.gif -->

<img src="{{ img_path('photos/hero') }}" alt="Hero">
<!-- finds photos/hero.png, etc. -->
```

## Fonts

Use `font_path()` to reference fonts in `assets/fonts/`. The helper automatically detects the file extension by searching for `.woff2`, `.woff`, `.ttf`, then `.otf`:

```jinja
@font-face {
  font-family: 'Inter';
  src: url('{{ font_path('inter') }}') format('woff2');
}
<!-- finds inter.woff2, inter.woff, inter.ttf, or inter.otf -->
```

## With root_url

All helpers respect the `root_url` setting in `medusa.yaml`. If you set:

```yaml
root_url: https://cdn.example.com
```

Then `css_path('main')` outputs `https://cdn.example.com/assets/css/main.css`.
