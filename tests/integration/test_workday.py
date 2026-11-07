from pathlib import Path

import pytest

from autoapply.browser.manager import BrowserManager
from autoapply.fill import fill_application
from autoapply.llm.client import MockLLMClient
from autoapply.llm.schemas import FreeTextDraft
from autoapply.profile import CandidateProfile
from test_sites.http import start_site

SITE = Path(__file__).resolve().parents[2] / "test_sites" / "workday_mock"


def _llm() -> MockLLMClient:
    return MockLLMClient(
        FreeTextDraft(
            answer="I wrote the first algorithm at Analytical Engine Co.",
            cited_fact_ids=["exp_001"],
            unsupported=False,
        )
    )


@pytest.mark.asyncio
async def test_workday_signup_does_not_click_create(
    sample_profile: CandidateProfile, tmp_path: Path
) -> None:
    server, url = start_site(SITE)
    try:
        async with BrowserManager(profile_dir=tmp_path / "wd1", headed=False) as browser:
            result = await fill_application(
                profile=sample_profile, url=url, llm=_llm(), browser=browser
            )
            page = browser.context.pages[0]
            assert result.status == "needs_input"
            assert await page.locator("#email").input_value() == sample_profile.email
            assert await page.locator("[data-automation-id='signupSection']").is_visible()
            assert result.submit_clicked is False
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.asyncio
async def test_workday_stops_before_submit(
    sample_profile: CandidateProfile, resume_path: Path, tmp_path: Path
) -> None:
    server, url = start_site(SITE)
    try:
        async with BrowserManager(profile_dir=tmp_path / "wd2", headed=False) as browser:
            result = await fill_application(
                profile=sample_profile,
                url=url + "?apply=1",
                llm=_llm(),
                browser=browser,
                resume_path=resume_path,
            )
            assert result.submit_clicked is False
            assert result.confirmation_visible is False
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.asyncio
async def test_workday_captcha_and_assessment_stop(
    sample_profile: CandidateProfile, tmp_path: Path
) -> None:
    server, url = start_site(SITE)
    try:
        async with BrowserManager(profile_dir=tmp_path / "wd3", headed=False) as browser:
            cap = await fill_application(
                profile=sample_profile, url=url + "captcha.html", llm=_llm(), browser=browser
            )
            assert cap.status == "needs_input"
            assess = await fill_application(
                profile=sample_profile,
                url=url + "assessment.html",
                llm=_llm(),
                browser=browser,
            )
            assert assess.status == "needs_input"
    finally:
        server.shutdown()
        server.server_close()
