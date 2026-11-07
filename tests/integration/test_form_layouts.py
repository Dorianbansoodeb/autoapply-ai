from __future__ import annotations

from pathlib import Path

import pytest

from autoapply.browser.manager import BrowserManager
from autoapply.fill import fill_application
from autoapply.llm.client import MockLLMClient
from autoapply.llm.schemas import FreeTextDraft
from autoapply.profile import CandidateProfile
from test_sites.http import start_site

SITES = Path(__file__).resolve().parents[2] / "test_sites"
LAYOUTS = ["multipage", "iframe", "dropdown", "validation"]


def _llm() -> MockLLMClient:
    return MockLLMClient(
        FreeTextDraft(
            answer="I wrote the first algorithm at Analytical Engine Co.",
            cited_fact_ids=["exp_001"],
            unsupported=False,
        )
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("layout", LAYOUTS)
async def test_layout_fills_and_stops(
    layout: str,
    sample_profile: CandidateProfile,
    resume_path: Path,
    tmp_path: Path,
) -> None:
    server, url = start_site(SITES / layout)
    try:
        llm = _llm()
        async with BrowserManager(profile_dir=tmp_path / layout, headed=False) as browser:
            result = await fill_application(
                profile=sample_profile,
                url=url,
                llm=llm,
                browser=browser,
                resume_path=resume_path,
            )
            page = browser.context.pages[0]
            assert result.submit_clicked is False
            assert result.confirmation_visible is False
            heading = page.get_by_role("heading", name="Application received")
            assert await heading.count() == 0
            submit = page.get_by_role("button", name="Submit application")
            # iframe: submit lives inside the frame
            if layout == "iframe":
                frame = page.frame_locator("iframe")
                assert await frame.get_by_label("Full name").input_value() == "Ada Lovelace"
                assert await frame.get_by_role("button", name="Submit application").count() == 1
            else:
                assert await page.get_by_label("Full name").input_value() == "Ada Lovelace"
                assert await submit.count() == 1
            assert "name" in result.filled_fields
            assert "email" in result.filled_fields
    finally:
        server.shutdown()
        server.server_close()
