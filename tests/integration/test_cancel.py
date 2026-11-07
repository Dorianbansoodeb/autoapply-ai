from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from autoapply.browser.manager import BrowserManager
from autoapply.cancel import CancelledError, CancelToken
from autoapply.fill import fill_application
from autoapply.llm.client import MockLLMClient
from autoapply.llm.schemas import FreeTextDraft
from autoapply.profile import CandidateProfile


@pytest.mark.asyncio
async def test_cancel_mid_fill_never_clicks_submit(
    sample_profile: CandidateProfile,
    resume_path: Path,
    simple_form_url: str,
    browser_profile_dir: Path,
) -> None:
    started = asyncio.Event()

    def on_call() -> None:
        started.set()

    llm = MockLLMClient(
        FreeTextDraft(answer="should not land", cited_fact_ids=["exp_001"], unsupported=False),
        delay_s=5,
        on_call=on_call,
    )
    token = CancelToken()

    async with BrowserManager(profile_dir=browser_profile_dir, headed=False) as browser:
        task = asyncio.create_task(
            fill_application(
                profile=sample_profile,
                url=simple_form_url,
                llm=llm,
                browser=browser,
                resume_path=resume_path,
                cancel=token,
            )
        )
        await asyncio.wait_for(started.wait(), timeout=10)
        token.cancel()
        with pytest.raises(CancelledError):
            await task

        page = browser.context.pages[0]
        assert await page.get_by_role("button", name="Submit application").count() == 1
        assert await page.get_by_role("heading", name="Application received").count() == 0
        cover = await page.get_by_label("Why do you want this role?").input_value()
        assert cover == ""
