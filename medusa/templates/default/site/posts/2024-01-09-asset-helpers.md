# Asset Path Helpers

Medusa provides convenient helper functions for referencing assets in your templates.

## CSS Files

Use `css_path()` to reference stylesheets in `assets/css/`. You can omit the `.css` extension or include it:

```jinja
<link rel="stylesheet" href="{{ css_path('main') }}">
<!-- outputs: /assets/css/main.css -->

<link rel="stylesheet" href="{{ css_path('main.css') }}">
<!-- also outputs: /assets/css/main.css -->

<link rel="stylesheet" href="{{ css_path('themes/dark') }}">
<!-- outputs: /assets/css/themes/dark.css -->
```

## JavaScript Files

Use `js_path()` to reference scripts in `assets/js/`. Extension is optional:

```jinja
<script src="{{ js_path('main') }}"></script>
<!-- outputs: /assets/js/main.js -->

<script src="{{ js_path('main.js') }}"></script>
<!-- also outputs: /assets/js/main.js -->

<script src="{{ js_path('vendor/alpine') }}"></script>
<!-- outputs: /assets/js/vendor/alpine.js -->
```

## Images

Use `img_path()` to reference images in `assets/images/`. You can pass the full filename with extension, or omit it and the helper will auto-detect by searching for `.png`, `.jpg`, `.jpeg`, then `.gif`:

```jinja
<img src="{{ img_path('logo.png') }}" alt="Logo">
<!-- outputs: /assets/images/logo.png -->

<img src="{{ img_path('logo') }}" alt="Logo">
<!-- auto-detects: finds logo.png, logo.jpg, logo.jpeg, or logo.gif -->

<img src="{{ img_path('photos/hero') }}" alt="Hero">
<!-- finds photos/hero.png, etc. -->
```

## Fonts

Use `font_path()` to reference fonts in `assets/fonts/`. You can pass the full filename with extension, or omit it and the helper will auto-detect by searching for `.woff2`, `.woff`, `.ttf`, then `.otf`:

```jinja
@font-face {
  font-family: 'Inter';
  src: url('{{ font_path('inter.woff2') }}') format('woff2');
}
<!-- outputs: /assets/fonts/inter.woff2 -->

@font-face {
  font-family: 'Inter';
  src: url('{{ font_path('inter') }}') format('woff2');
}
<!-- auto-detects: finds inter.woff2, inter.woff, inter.ttf, or inter.otf -->
```

## With root_url

All helpers respect the `root_url` setting in `medusa.yaml`. If you set:

```yaml
root_url: https://cdn.example.com
```

Then `css_path('main')` outputs `https://cdn.example.com/assets/css/main.css`.
