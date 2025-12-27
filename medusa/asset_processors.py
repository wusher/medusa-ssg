"""Asset processors for Medusa.

This module contains implementations of the AssetProcessor protocol
for different asset types. Each processor handles a single type of asset,
following the Single Responsibility Principle (SRP).

Key classes:
- ImageProcessor: Optimizes image files.
- CSSProcessor: Processes CSS files (excludes Tailwind-managed files).
- JSProcessor: Minifies JavaScript files.
- StaticAssetProcessor: Copies static assets without modification.
- TailwindProcessor: Processes Tailwind CSS.
- AssetProcessorRegistry: Registry for managing asset processors.
"""

from __future__ import annotations

import shutil
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path

from .executable_utils import find_executable

try:
    from rjsmin import jsmin
except ImportError:  # pragma: no cover
    jsmin = None

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None


class BaseAssetProcessor(ABC):
    """Base class for asset processors.

    This abstract base class defines the interface for asset processors
    and provides common functionality. Each subclass handles a specific
    type of asset, following the Single Responsibility Principle.

    Provides shared utilities:
        - ensure_dest_dir: Creates parent directories for output files.
    """

    @property
    @abstractmethod
    def priority(self) -> int:
        """Return processor priority (higher = checked first)."""
        ...

    @abstractmethod
    def can_process(self, path: Path) -> bool:
        """Check if this processor can handle the given asset.

        Args:
            path: Path to the asset file.

        Returns:
            True if this processor can handle the asset.
        """
        ...

    @abstractmethod
    def process(self, source: Path, dest: Path) -> bool:
        """Process an asset file.

        Args:
            source: Source asset path.
            dest: Destination path for processed asset.

        Returns:
            True if processing was successful.
        """
        ...

    def ensure_dest_dir(self, dest: Path) -> None:
        """Ensure the parent directory of the destination exists.

        This is a shared utility method to reduce duplication across
        processor implementations. Should be called at the start of
        each process() method.

        Args:
            dest: Destination file path.
        """
        dest.parent.mkdir(parents=True, exist_ok=True)


class ImageProcessor(BaseAssetProcessor):
    """Optimizes image files using PIL.

    Supports PNG, JPG, JPEG, and WebP formats. Falls back to
    simple copying if PIL is not available.
    """

    SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

    @property
    def priority(self) -> int:
        return 100

    def can_process(self, path: Path) -> bool:
        """Check if this is a supported image file."""
        return path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def process(self, source: Path, dest: Path) -> bool:
        """Optimize and copy image file.

        Args:
            source: Source image path.
            dest: Destination path.

        Returns:
            True if processing was successful.
        """
        self.ensure_dest_dir(dest)

        if Image is not None:
            try:
                with Image.open(source) as img:
                    img.save(dest, optimize=True)
                return True
            except Exception:
                pass

        # Fallback: simple copy
        shutil.copy2(source, dest)
        return True


class CSSProcessor(BaseAssetProcessor):
    """Processes CSS files.

    Excludes main.css which is handled by TailwindProcessor.
    Other CSS files are copied directly.
    """

    @property
    def priority(self) -> int:
        return 90

    def can_process(self, path: Path) -> bool:
        """Check if this is a CSS file (but not main.css for Tailwind)."""
        return path.suffix.lower() == ".css" and path.name != "main.css"

    def process(self, source: Path, dest: Path) -> bool:
        """Copy CSS file to destination.

        Args:
            source: Source CSS path.
            dest: Destination path.

        Returns:
            True if processing was successful.
        """
        self.ensure_dest_dir(dest)
        shutil.copy2(source, dest)
        return True


class TailwindCSSProcessor(BaseAssetProcessor):
    """Processes Tailwind CSS using the CLI tool.

    Handles main.css specifically, running through the Tailwind CLI
    for JIT compilation. Falls back to copying if Tailwind is not available.
    """

    def __init__(self, project_root: Path, output_dir: Path):
        """Initialize the Tailwind processor.

        Args:
            project_root: Root directory of the project.
            output_dir: Output directory for processed assets.
        """
        self.project_root = project_root
        self.output_dir = output_dir

    @property
    def priority(self) -> int:
        return 95  # Higher than CSSProcessor to catch main.css first

    def can_process(self, path: Path) -> bool:
        """Check if this is the Tailwind main.css file."""
        return path.suffix.lower() == ".css" and path.name == "main.css"

    def process(self, source: Path, dest: Path) -> bool:
        """Process Tailwind CSS.

        Args:
            source: Source CSS path (main.css).
            dest: Destination path.

        Returns:
            True if processing was successful.
        """
        self.ensure_dest_dir(dest)

        tailwind_bin = find_executable("tailwindcss", self.project_root)
        if not tailwind_bin:
            print("Tailwind CSS CLI not found; skipping CSS build.")
            print(
                "Install with `npm install -g tailwindcss` or `npm install -D tailwindcss` in the project. "
                "Falling back to unprocessed CSS."
            )
            shutil.copy2(source, dest)
            return True

        content_globs = [
            str(self.project_root / "site" / "**" / "*.md"),
            str(self.project_root / "site" / "**" / "*.jinja"),
            str(self.project_root / "assets" / "**" / "*.js"),
        ]

        cmd = [
            tailwind_bin,
            "-i",
            str(source),
            "-o",
            str(dest),
            "--minify",
            "--content",
            ",".join(content_globs),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print("Tailwind build failed:", result.stderr.strip())
            shutil.copy2(source, dest)

        return True


class JSProcessor(BaseAssetProcessor):
    """Minifies JavaScript files.

    Uses rjsmin if available, falls back to terser, then to simple copying.
    """

    def __init__(self, project_root: Path):
        """Initialize the JS processor.

        Args:
            project_root: Root directory of the project.
        """
        self.project_root = project_root

    @property
    def priority(self) -> int:
        return 80

    def can_process(self, path: Path) -> bool:
        """Check if this is a JavaScript file."""
        return path.suffix.lower() == ".js"

    def process(self, source: Path, dest: Path) -> bool:
        """Minify and copy JavaScript file.

        Args:
            source: Source JS path.
            dest: Destination path.

        Returns:
            True if processing was successful.
        """
        self.ensure_dest_dir(dest)

        # Try rjsmin first
        if jsmin is not None:
            try:
                with open(source, encoding="utf-8") as f_in:
                    minified = jsmin(f_in.read())
                with open(dest, "w", encoding="utf-8") as f_out:
                    f_out.write(minified)
                return True
            except Exception:
                pass

        # Try terser
        terser = find_executable("terser", self.project_root)
        if terser:
            result = subprocess.run(
                [terser, str(source), "-c", "-m", "-o", str(dest)],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return True
            print("JS minification failed via terser:", result.stderr.strip())

        # Fallback: simple copy
        shutil.copy2(source, dest)
        return True


class StaticAssetProcessor(BaseAssetProcessor):
    """Copies static assets without modification.

    This is the fallback processor for assets that don't need
    special processing (fonts, SVGs, etc.).
    """

    @property
    def priority(self) -> int:
        return 0  # Lowest priority - fallback

    def can_process(self, path: Path) -> bool:
        """Accept any file as a fallback."""
        return True

    def process(self, source: Path, dest: Path) -> bool:
        """Copy file to destination.

        Args:
            source: Source file path.
            dest: Destination path.

        Returns:
            True if processing was successful.
        """
        self.ensure_dest_dir(dest)
        shutil.copy2(source, dest)
        return True


class AssetProcessorRegistry:
    """Registry for managing asset processors.

    This registry implements the Open/Closed Principle - new processors
    can be added without modifying existing code. It also provides
    a strategy pattern for selecting the appropriate processor.
    """

    def __init__(self):
        """Initialize an empty registry."""
        self._processors: list[BaseAssetProcessor] = []

    def register(self, processor: BaseAssetProcessor) -> None:
        """Register a new processor.

        Processors are stored sorted by priority (highest first).

        Args:
            processor: Asset processor to register.
        """
        self._processors.append(processor)
        self._processors.sort(key=lambda p: p.priority, reverse=True)

    def get_processor(self, path: Path) -> BaseAssetProcessor | None:
        """Get the appropriate processor for a file.

        Args:
            path: Path to the asset file.

        Returns:
            The first processor that can handle the file, or None.
        """
        for processor in self._processors:
            if processor.can_process(path):
                return processor
        return None

    def process(self, source: Path, dest: Path) -> bool:
        """Process an asset using the appropriate processor.

        Args:
            source: Source asset path.
            dest: Destination path.

        Returns:
            True if processing was successful, False if no processor found.
        """
        processor = self.get_processor(source)
        if processor:
            return processor.process(source, dest)
        return False


def create_default_registry(
    project_root: Path, output_dir: Path
) -> AssetProcessorRegistry:
    """Create a registry with default processors.

    Args:
        project_root: Root directory of the project.
        output_dir: Output directory for processed assets.

    Returns:
        Configured AssetProcessorRegistry.
    """
    registry = AssetProcessorRegistry()
    registry.register(ImageProcessor())
    registry.register(TailwindCSSProcessor(project_root, output_dir))
    registry.register(CSSProcessor())
    registry.register(JSProcessor(project_root))
    registry.register(StaticAssetProcessor())
    return registry
