"""Playwright persistent headed context with a dedicated profile directory."""

from __future__ import annotations

from pathlib import Path
from types import TracebackType

from playwright.async_api import BrowserContext, Page, Playwright, async_playwright

DEFAULT_DATA_ROOT = Path.home() / "AutoApplyAI"
DEFAULT_BROWSER_PROFILE = DEFAULT_DATA_ROOT / "browser-profile"


class BrowserManager:
    """Owns a Chromium persistent context.

    Headed is the product default. Tests pass headed=False. The browser is
    never shared with the user's daily Chrome profile.
    """

    def __init__(
        self,
        profile_dir: Path | None = None,
        *,
        headed: bool = True,
    ) -> None:
        self.profile_dir = Path(profile_dir or DEFAULT_BROWSER_PROFILE)
        self.headed = headed
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None

    @property
    def context(self) -> BrowserContext:
        if self._context is None:
            raise RuntimeError("BrowserManager is not started")
        return self._context

    async def start(self) -> BrowserContext:
        if self._context is not None:
            return self._context
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = await async_playwright().start()
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.profile_dir),
            headless=not self.headed,
            viewport={"width": 1280, "height": 900},
            accept_downloads=False,
        )
        return self._context

    async def new_page(self) -> Page:
        await self.start()
        page = await self.context.new_page()
        return page

    async def close(self) -> None:
        if self._context is not None:
            await self._context.close()
            self._context = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None

    async def __aenter__(self) -> BrowserManager:
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()
