"""Asset path resolver for Medusa.

This module provides the AssetPathResolver class for resolving asset paths
to URLs. It is extracted from TemplateEngine to follow the Single
Responsibility Principle (SRP).

Key classes:
- DefaultAssetPathResolver: Resolves asset paths for templates.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path


class AssetNotFoundError(Exception):
    """Error raised when an asset file is not found.

    Attributes:
        asset_name: The name of the asset that was requested.
        asset_type: The type of asset (e.g., "image", "font", "js", "css").
        searched_paths: List of paths that were searched.
    """

    def __init__(
        self,
        asset_name: str,
        asset_type: str,
        searched_paths: list[Path],
    ):
        self.asset_name = asset_name
        self.asset_type = asset_type
        self.searched_paths = searched_paths
        paths_str = ", ".join(str(p) for p in searched_paths)
        super().__init__(
            f"{asset_type} asset '{asset_name}' not found. Searched: {paths_str}"
        )


class DefaultAssetPathResolver:
    """Resolves asset paths to URLs.

    This class is responsible for finding assets and generating
    their URL paths. It follows the Single Responsibility Principle -
    only handles asset path resolution.

    Attributes:
        site_dir: Directory containing site content.
        url_generator: Function to generate URLs with root_url prefix.
    """

    # Supported extensions for auto-detection
    IMAGE_EXTENSIONS = ("png", "jpg", "jpeg", "gif", "svg", "webp")
    FONT_EXTENSIONS = ("woff2", "woff", "ttf", "otf", "eot")

    def __init__(
        self, site_dir: Path, url_generator: Callable[[str], str] | None = None
    ):
        """Initialize the asset path resolver.

        Args:
            site_dir: Directory containing site content.
            url_generator: Optional function to generate URLs.
        """
        self.site_dir = site_dir
        self.assets_dir = site_dir.parent / "assets"
        self._url_generator = url_generator or (lambda x: x)

    def set_url_generator(self, url_generator: Callable[[str], str]) -> None:
        """Set the URL generator function.

        Args:
            url_generator: Function to generate URLs with root_url prefix.
        """
        self._url_generator = url_generator

    def resolve(self, name: str, asset_type: str) -> str:
        """Resolve an asset name to its URL path.

        Args:
            name: Asset filename (with or without extension).
            asset_type: Type of asset ('js', 'css', 'image', 'font').

        Returns:
            URL path to the asset.

        Raises:
            AssetNotFoundError: If the asset doesn't exist.
        """
        if asset_type == "js":
            return self._resolve_js(name)
        elif asset_type == "css":
            return self._resolve_css(name)
        elif asset_type == "image":
            return self._resolve_image(name)
        elif asset_type == "font":
            return self._resolve_font(name)
        else:
            raise ValueError(f"Unknown asset type: {asset_type}")

    def js_path(self, name: str) -> str:
        """Return URL path for a JavaScript file.

        Args:
            name: Filename with or without extension (e.g., "app" or "app.js").

        Returns:
            URL path like /assets/js/app.js

        Raises:
            AssetNotFoundError: If the JavaScript file doesn't exist.
        """
        return self._resolve_js(name)

    def css_path(self, name: str) -> str:
        """Return URL path for a CSS file.

        Args:
            name: Filename with or without extension (e.g., "main" or "main.css").

        Returns:
            URL path like /assets/css/main.css

        Raises:
            AssetNotFoundError: If the CSS file doesn't exist.
        """
        return self._resolve_css(name)

    def img_path(self, name: str) -> str:
        """Return URL path for an image file, auto-detecting extension.

        Searches for the image with extensions in order: png, jpg, jpeg, gif, svg, webp.
        If name already has an extension, validates it exists.

        Args:
            name: Filename with or without extension (e.g., "logo" or "logo.png").

        Returns:
            URL path like /assets/images/logo.png

        Raises:
            AssetNotFoundError: If no matching image file is found.
        """
        return self._resolve_image(name)

    def font_path(self, name: str) -> str:
        """Return URL path for a font file, auto-detecting extension.

        Searches for the font with extensions in order: woff2, woff, ttf, otf, eot.
        If name already has an extension, validates it exists.

        Args:
            name: Filename with or without extension (e.g., "inter" or "inter.woff2").

        Returns:
            URL path like /assets/fonts/inter.woff2

        Raises:
            AssetNotFoundError: If no matching font file is found.
        """
        return self._resolve_font(name)

    def _resolve_js(self, name: str) -> str:
        """Resolve JavaScript file path."""
        if not name.endswith(".js"):
            name = f"{name}.js"
        file_path = self.assets_dir / "js" / name
        if not file_path.exists():
            raise AssetNotFoundError(name, "JavaScript", [file_path])
        return self._url_generator(f"/assets/js/{name}")

    def _resolve_css(self, name: str) -> str:
        """Resolve CSS file path."""
        if not name.endswith(".css"):
            name = f"{name}.css"
        file_path = self.assets_dir / "css" / name
        if not file_path.exists():
            raise AssetNotFoundError(name, "CSS", [file_path])
        return self._url_generator(f"/assets/css/{name}")

    def _resolve_image(self, name: str) -> str:
        """Resolve image file path with auto-detection."""
        assets_dir = self.assets_dir / "images"

        # If already has a known image extension, validate it exists
        for ext in self.IMAGE_EXTENSIONS:
            if name.endswith(f".{ext}"):
                file_path = assets_dir / name
                if not file_path.exists():
                    raise AssetNotFoundError(name, "image", [file_path])
                return self._url_generator(f"/assets/images/{name}")

        # Auto-detect extension
        searched_paths = []
        for ext in self.IMAGE_EXTENSIONS:
            file_path = assets_dir / f"{name}.{ext}"
            searched_paths.append(file_path)
            if file_path.exists():
                return self._url_generator(f"/assets/images/{name}.{ext}")

        raise AssetNotFoundError(name, "image", searched_paths)

    def _resolve_font(self, name: str) -> str:
        """Resolve font file path with auto-detection."""
        assets_dir = self.assets_dir / "fonts"

        # If already has a known font extension, validate it exists
        for ext in self.FONT_EXTENSIONS:
            if name.endswith(f".{ext}"):
                file_path = assets_dir / name
                if not file_path.exists():
                    raise AssetNotFoundError(name, "font", [file_path])
                return self._url_generator(f"/assets/fonts/{name}")

        # Auto-detect extension
        searched_paths = []
        for ext in self.FONT_EXTENSIONS:
            file_path = assets_dir / f"{name}.{ext}"
            searched_paths.append(file_path)
            if file_path.exists():
                return self._url_generator(f"/assets/fonts/{name}.{ext}")

        raise AssetNotFoundError(name, "font", searched_paths)
