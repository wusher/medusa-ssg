"""HTML utility functions for Medusa.

This module provides HTML manipulation utilities including escaping,
URL absolutization, and other HTML-related operations.

Following the Single Responsibility Principle, this module focuses
exclusively on HTML string manipulation.

Functions:
    escape_html: Escape special HTML characters in a string.
    absolutize_html_urls: Convert relative URLs to absolute in HTML.
    join_root_url: Join a base URL with a path.
"""

from __future__ import annotations

import re

# URL attribute regex pattern for finding href, src, action attributes
_URL_ATTR_RE = re.compile(
    r'(?P<prefix>\b(?:href|src|action)=["\'])(?P<url>[^"\']+)(?P<suffix>["\'])'
)

# URL prefixes that should not be modified
_URL_SKIP_PREFIXES = (
    "http://",
    "https://",
    "//",
    "mailto:",
    "tel:",
    "#",
    "javascript:",
)


def escape_html(text: str) -> str:
    """Escape special HTML characters in a string.

    Converts the following characters to their HTML entity equivalents:
    - & becomes &amp;
    - < becomes &lt;
    - > becomes &gt;
    - " becomes &quot;

    Args:
        text: The string to escape.

    Returns:
        The escaped string, safe for inclusion in HTML.

    Examples:
        >>> escape_html('<script>alert("XSS")</script>')
        '&lt;script&gt;alert(&quot;XSS&quot;)&lt;/script&gt;'

        >>> escape_html('Tom & Jerry')
        'Tom &amp; Jerry'
    """
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def join_root_url(root_url: str, path: str) -> str:
    """Safely join a root URL and a path, avoiding double slashes.

    Args:
        root_url: Base URL (e.g., https://example.com/blog).
        path: Path beginning with or without a leading slash.

    Returns:
        Combined URL with proper slash handling.

    Examples:
        >>> join_root_url('https://example.com', '/about')
        'https://example.com/about'

        >>> join_root_url('https://example.com/', 'about')
        'https://example.com/about'
    """
    if not root_url:
        return path
    base = root_url.rstrip("/")
    suffix = path if path.startswith("/") else f"/{path}"
    return f"{base}{suffix}"


def absolutize_html_urls(html: str, root_url: str) -> str:
    """Rewrite root-relative URLs in HTML to absolute URLs.

    Processes href, src, and action attributes in HTML, converting
    root-relative URLs (starting with /) to absolute URLs using the
    provided root_url. External URLs, anchors, mailto/tel links, and
    javascript: URLs are left unchanged.

    Args:
        html: HTML content to process.
        root_url: Base URL to prepend to relative paths.

    Returns:
        HTML with relative URLs converted to absolute.

    Examples:
        >>> absolutize_html_urls('<a href="/about">About</a>', 'https://example.com')
        '<a href="https://example.com/about">About</a>'

        >>> absolutize_html_urls('<a href="https://other.com">Other</a>', 'https://example.com')
        '<a href="https://other.com">Other</a>'
    """
    if not root_url:
        return html

    def repl(match: re.Match) -> str:
        url = match.group("url")
        if not url or url.startswith(_URL_SKIP_PREFIXES):
            return match.group(0)
        absolute = join_root_url(root_url, url)
        return f"{match.group('prefix')}{absolute}{match.group('suffix')}"

    return _URL_ATTR_RE.sub(repl, html)
