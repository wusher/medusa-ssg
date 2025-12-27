"""Medusa static site generator.

This package provides a minimal static site generator that uses Markdown and Jinja2 templates.
It supports features like asset processing, content management, templating, and development server with live reload.

The main entry point is the CLI module, which provides commands for scaffolding new projects,
building sites, and running the development server.

Architecture follows SOLID principles:
- Single Responsibility: Each module handles one concern (content, templates, assets, etc.)
- Open/Closed: Registries and protocols allow extension without modification
- Liskov Substitution: Protocol implementations are interchangeable
- Interface Segregation: Small, focused interfaces for each component type
- Dependency Inversion: High-level modules depend on abstractions (protocols)
"""

__all__ = ["__version__"]
__version__ = "0.1.2"
