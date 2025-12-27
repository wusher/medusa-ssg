"""Protocol definitions for Medusa.

This module defines the interfaces (protocols) used throughout Medusa,
following the Dependency Inversion Principle (DIP) of SOLID.

These protocols enable:
- Loose coupling between components
- Easy testing through mock implementations
- Extensibility without modifying existing code (Open/Closed Principle)
"""

from __future__ import annotations

from abc import abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .content import Heading, Page


@runtime_checkable
class ContentRenderer(Protocol):
    """Protocol for rendering content from source files.

    Implementations handle specific content types (Markdown, HTML, Jinja).
    This follows the Single Responsibility Principle - each renderer
    handles one content type.
    """

    @abstractmethod
    def can_render(self, path: Path) -> bool:
        """Check if this renderer can handle the given file.

        Args:
            path: Path to the source file.

        Returns:
            True if this renderer can process the file.
        """
        ...

    @abstractmethod
    def render(self, content: str, folder: str) -> tuple[str, list[Heading]]:
        """Render content to HTML.

        Args:
            content: Source content to render.
            folder: Folder containing the page (for relative path resolution).

        Returns:
            Tuple of (rendered HTML, list of headings for TOC).
        """
        ...

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Return the source type identifier (e.g., 'markdown', 'html', 'jinja')."""
        ...


@runtime_checkable
class MetadataExtractor(Protocol):
    """Protocol for extracting metadata from content.

    Implementations extract specific types of metadata (title, tags, date, etc.).
    This follows ISP - clients only depend on extractors they need.
    """

    @abstractmethod
    def extract(self, content: str, path: Path) -> dict[str, Any]:
        """Extract metadata from content.

        Args:
            content: Source content.
            path: Path to the source file.

        Returns:
            Dictionary of extracted metadata.
        """
        ...


@runtime_checkable
class AssetProcessor(Protocol):
    """Protocol for processing assets.

    Implementations handle specific asset types (CSS, JS, images).
    This follows OCP - new asset types can be added without modifying
    existing processors.
    """

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

    @property
    @abstractmethod
    def priority(self) -> int:
        """Return processor priority (higher = checked first)."""
        ...


@runtime_checkable
class AssetPathResolver(Protocol):
    """Protocol for resolving asset paths to URLs.

    This separates asset path resolution from template rendering (SRP).
    """

    @abstractmethod
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
        ...


@runtime_checkable
class TemplateRenderer(Protocol):
    """Protocol for rendering templates.

    This defines the interface for template rendering engines,
    allowing different implementations (Jinja2, Mako, etc.).
    """

    @abstractmethod
    def render_page(self, page: Page) -> str:
        """Render a page with its layout.

        Args:
            page: Page object to render.

        Returns:
            Rendered HTML string.
        """
        ...

    @abstractmethod
    def render_string(self, template: str, context: dict[str, Any]) -> str:
        """Render a template string.

        Args:
            template: Template string to render.
            context: Variables to make available in the template.

        Returns:
            Rendered string.
        """
        ...


@runtime_checkable
class ContentLoader(Protocol):
    """Protocol for loading content files.

    This separates file discovery from content processing (SRP).
    """

    @abstractmethod
    def iter_files(self, include_drafts: bool = False) -> list[Path]:
        """Iterate over all content files.

        Args:
            include_drafts: Whether to include draft files.

        Returns:
            List of paths to content files.
        """
        ...


@runtime_checkable
class PageBuilder(Protocol):
    """Protocol for building Page objects.

    This separates page construction from content loading (SRP).
    """

    @abstractmethod
    def build(self, path: Path, draft: bool = False) -> Page:
        """Build a Page object from a source file.

        Args:
            path: Path to the source file.
            draft: Whether this is a draft page.

        Returns:
            Page object.
        """
        ...
