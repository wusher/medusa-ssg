"""Asset processing pipeline for Medusa.

This module handles the processing and optimization of static assets such as CSS, JavaScript, and images.
It includes functionality for copying assets, processing Tailwind CSS, and minifying JavaScript.

Key components:
- AssetPipeline: Main class for managing asset processing workflow.
- Individual processors in asset_processors module for each asset type.

Design principles:
- Single Responsibility: Each processor handles one asset type.
- Open/Closed: New asset types can be added via the processor registry.
- Dependency Inversion: Pipeline depends on processor abstractions.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .asset_processors import (
    AssetProcessorRegistry,
    JSProcessor,
    TailwindCSSProcessor,
    create_default_registry,
)

# Keep these imports for backward compatibility
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

    The pipeline now delegates to individual asset processors, following
    the Single Responsibility Principle. New asset types can be added
    by registering additional processors (Open/Closed Principle).

    Attributes:
        project_root (Path): Root directory of the project.
        assets_dir (Path): Directory containing source assets.
        output_dir (Path): Directory where processed assets are written.
        processor_registry (AssetProcessorRegistry): Registry of asset processors.
    """

    def __init__(
        self,
        project_root: Path,
        output_dir: Path,
        processor_registry: AssetProcessorRegistry | None = None,
    ):
        """Initialize the asset pipeline.

        Args:
            project_root: Root directory of the Medusa project.
            output_dir: Directory where built assets will be placed.
            processor_registry: Optional custom processor registry.
        """
        self.project_root = project_root
        self.assets_dir = project_root / "assets"
        self.output_dir = output_dir
        self.processor_registry = processor_registry or create_default_registry(
            project_root, output_dir
        )

    def run(self) -> None:
        """Execute the asset processing pipeline.

        This method processes all assets using the registered processors.
        It handles Tailwind CSS separately to ensure proper content scanning.
        """
        if not self.assets_dir.exists():
            return

        target = self.output_dir / "assets"
        target.mkdir(parents=True, exist_ok=True)

        # Process all assets through the registry
        for item in self.assets_dir.rglob("*"):
            if item.is_dir():
                continue

            rel = item.relative_to(self.assets_dir)
            dest = target / rel

            # Skip main.css - handled specially by TailwindCSSProcessor
            if item.suffix == ".css" and item.name == "main.css":
                continue

            self.processor_registry.process(item, dest)

        # Process Tailwind CSS separately (needs special handling)
        self._process_tailwind()

    def _process_tailwind(self) -> None:
        """Process Tailwind CSS using the dedicated processor.

        This is called separately because Tailwind needs to scan all
        content files for class names, not just the CSS file.
        """
        input_css = self.assets_dir / "css" / "main.css"
        if not input_css.exists():
            return

        output_css = self.output_dir / "assets" / "css" / "main.css"

        # Use the TailwindCSSProcessor from the registry
        tailwind_processor = TailwindCSSProcessor(self.project_root, self.output_dir)
        tailwind_processor.process(input_css, output_css)

    # Legacy methods for backward compatibility (deprecated)
    def _copy_static_assets(self) -> None:  # pragma: no cover
        """Copy static assets from assets_dir to output_dir.

        Deprecated: The run() method now handles all asset processing
        through the processor registry.
        """
        target = self.output_dir / "assets"
        target.mkdir(parents=True, exist_ok=True)
        for item in self.assets_dir.rglob("*"):
            if item.is_dir():
                continue
            rel = item.relative_to(self.assets_dir)
            dest = target / rel
            if item.suffix == ".css" and item.name == "main.css":
                continue
            self.processor_registry.process(item, dest)

    def _minify_js(self) -> None:
        """Minify JavaScript files using the JS processor.

        Deprecated: JavaScript processing is now handled by the
        JSProcessor in the registry.
        """
        js_processor = JSProcessor(self.project_root)
        target = self.output_dir / "assets"
        for js_file in self.assets_dir.rglob("*.js"):
            rel = js_file.relative_to(self.assets_dir)
            dest = target / rel
            js_processor.process(js_file, dest)

    def _find_executable(self, name: str) -> str | None:  # pragma: no cover
        """Find an executable in PATH or local node_modules.

        Deprecated: Each processor now handles its own executable discovery.
        """
        found = shutil.which(name)
        if found:
            return found
        local = self.project_root / "node_modules" / ".bin" / name
        if local.exists():
            return str(local)
        return None
