"""URL policy. The LLM stays on localhost. The browser may open a user-supplied job URL."""

from __future__ import annotations

from urllib.parse import urlparse

class UrlNotAllowed(ValueError):
    """Raised when a URL is not allowed for this action."""


_LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1"})
_BLOCKED_BROWSER_HOSTS = frozenset(
    {
        "chatgpt.com",
        "chat.openai.com",
        "openai.com",
        "api.openai.com",
        "cursor.com",
        "www.cursor.com",
        "claude.ai",
        "gemini.google.com",
    }
)


def _parse(url: str):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise UrlNotAllowed(f"unsupported URL scheme: {parsed.scheme!r}")
    if parsed.username or parsed.password:
        raise UrlNotAllowed("URLs must not contain credentials")
    host = (parsed.hostname or "").lower()
    if not host:
        raise UrlNotAllowed("URL has no host")
    return parsed, host


def assert_localhost_url(url: str) -> None:
    """LLM endpoints and local mock servers only."""
    _parsed, host = _parse(url)
    if host not in _LOOPBACK:
        raise UrlNotAllowed(f"LLM and local tools only allow localhost; got host {host!r}")


def assert_browser_url(url: str) -> None:
    """Application pages the user asked to open.

    Unknown sites are allowed in assisted mode (user clicks Submit). ChatGPT,
    Cursor, and similar inference sites are never automated.
    """
    _parsed, host = _parse(url)
    if host in _BLOCKED_BROWSER_HOSTS or host.endswith(".openai.com"):
        raise UrlNotAllowed(
            f"refusing to automate {host}; it is not a job-application site"
        )
