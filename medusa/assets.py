"""Asset processing pipeline for Medusa.

This module handles the processing and optimization of static assets such as CSS, JavaScript, and images.
It includes functionality for copying assets, processing Tailwind CSS, and minifying JavaScript.

Key components:
- AssetPipeline: Main class for managing asset processing workflow.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Iterable

try:
    from rjsmin import jsmin
except ImportError:  # pragma: no cover - optional dependency in dev environments
    jsmin = None

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None


class AssetPipeline:
    """Handles the processing and optimization of static assets for the site.

    This class manages the asset pipeline, including copying static files,
    processing Tailwind CSS, and minifying JavaScript files.

    Attributes:
        project_root (Path): Root directory of the project.
        assets_dir (Path): Directory containing source assets.
        output_dir (Path): Directory where processed assets are written.
    """

    def __init__(self, project_root: Path, output_dir: Path):
        """Initialize the asset pipeline.

        Args:
            project_root: Root directory of the Medusa project.
            output_dir: Directory where built assets will be placed.
        """
        self.project_root = project_root
        self.assets_dir = project_root / "assets"
        self.output_dir = output_dir

    def run(self) -> None:
        """Execute the asset processing pipeline.

        This method copies static assets, processes Tailwind CSS if available,
        and minifies JavaScript files.
        """
        if not self.assets_dir.exists():
            return
        self._copy_static_assets()
        self._process_tailwind()
        self._minify_js()

    def _copy_static_assets(self) -> None:
        """Copy static assets from assets_dir to output_dir.

        Handles image optimization using PIL if available, and excludes
        main.css which is processed by Tailwind.
        """
        target = self.output_dir / "assets"
        target.mkdir(parents=True, exist_ok=True)
        for item in self.assets_dir.rglob("*"):
            if item.is_dir():
                continue
            rel = item.relative_to(self.assets_dir)
            dest = target / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            if item.suffix == ".css" and item.name == "main.css":
                # CSS handled by tailwind build step
                continue
            if Image and item.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                with Image.open(item) as img:
                    img.save(dest, optimize=True)
            else:
                shutil.copy2(item, dest)

    def _process_tailwind(self) -> None:
        """Process Tailwind CSS using the CLI tool.

        Builds the main.css file with content from site and assets directories.
        Requires tailwindcss CLI to be installed.
        """
        input_css = self.assets_dir / "css" / "main.css"
        if not input_css.exists():
            return
        output_css = self.output_dir / "assets" / "css" / "main.css"
        output_css.parent.mkdir(parents=True, exist_ok=True)
        tailwind_bin = shutil.which("tailwindcss")
        if not tailwind_bin:
            print("Tailwind CSS CLI not found; skipping CSS build.")
            return
        content_globs = [
            str(self.project_root / "site" / "**" / "*.md"),
            str(self.project_root / "site" / "**" / "*.html.jinja"),
            str(self.project_root / "assets" / "**" / "*.js"),
        ]
        cmd = [
            tailwind_bin,
            "-i",
            str(input_css),
            "-o",
            str(output_css),
            "--minify",
            "--content",
            ",".join(content_globs),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print("Tailwind build failed:", result.stderr.strip())

    def _minify_js(self) -> None:
        """Minify JavaScript files using rjsmin.

        Processes all .js files in the assets directory and writes minified
        versions to the output directory. Requires rjsmin to be installed.
        """
        if jsmin is None:
            return
        target = self.output_dir / "assets"
        for js_file in self.assets_dir.rglob("*.js"):
            rel = js_file.relative_to(self.assets_dir)
            dest = target / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(js_file, "r", encoding="utf-8") as f_in:
                minified = jsmin(f_in.read())
            with open(dest, "w", encoding="utf-8") as f_out:
                f_out.write(minified)
