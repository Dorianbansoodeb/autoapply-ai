"""Fill an application and stop before Submit."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from autoapply.browser.engine import FillState, fill_page
from autoapply.browser.manager import BrowserManager
from autoapply.cancel import CancelToken, CancelledError
from autoapply.llm.client import LLMClient
from autoapply.llm.schemas import FreeTextDraft
from autoapply.profile import CandidateProfile
from autoapply.urls import assert_browser_url


class FillResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ready_for_review", "needs_input", "cancelled", "blocked"]
    filled_fields: list[str] = Field(default_factory=list)
    pending_review: list[str] = Field(default_factory=list)
    submit_clicked: bool = False
    confirmation_visible: bool = False
    draft: FreeTextDraft | None = None
    notes: list[str] = Field(default_factory=list)


async def fill_application(
    *,
    profile: CandidateProfile,
    url: str,
    llm: LLMClient,
    browser: BrowserManager,
    resume_path: Path | None = None,
    cancel: CancelToken | None = None,
) -> FillResult:
    assert_browser_url(url)
    token = cancel or CancelToken()
    token.raise_if_cancelled()

    result = FillResult(status="ready_for_review", submit_clicked=False)
    await browser.start()
    token.raise_if_cancelled()
    page = browser.context.pages[0] if browser.context.pages else await browser.new_page()
    await page.goto(url, wait_until="domcontentloaded")
    assert_browser_url(page.url)
    token.raise_if_cancelled()
    state = FillState()

    try:
        await fill_page(
            page, profile, llm, resume_path=resume_path, token=token, state=state
        )
        result.filled_fields = state.filled
        result.pending_review = state.pending_review
        result.notes = state.notes
        result.draft = state.draft
        result.confirmation_visible = await _confirmation_visible(page)
        if state.stopped_for_human:
            result.status = "needs_input"
        if result.confirmation_visible:
            result.status = "blocked"
            result.notes.append("Confirmation page visible without a Submit click")
        elif "cover" not in result.filled_fields and any(
            "failed" in note.lower() for note in result.notes
        ):
            result.status = "needs_input"
        return result
    except CancelledError:
        result.status = "cancelled"
        result.notes.append("Fill cancelled; Submit was not clicked")
        raise


async def _confirmation_visible(page) -> bool:
    heading = page.get_by_role("heading", name="Application received")
    return await heading.count() > 0
