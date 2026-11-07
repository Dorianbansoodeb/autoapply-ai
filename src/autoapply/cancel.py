"""Cooperative cancellation. Never cancel-and-retry across a submit click."""

from __future__ import annotations

import asyncio


class CancelledError(Exception):
    """Raised when a cancel token fires between steps or mid-LLM call."""


class CancelToken:
    def __init__(self) -> None:
        self._event = asyncio.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    async def wait(self) -> None:
        await self._event.wait()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise CancelledError("operation cancelled")
