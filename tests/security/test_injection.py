from pathlib import Path

import pytest

from autoapply.browser.manager import BrowserManager
from autoapply.fill import fill_application
from autoapply.llm.client import MockLLMClient
from autoapply.llm.schemas import FreeTextDraft
from autoapply.profile import CandidateProfile
from test_sites.http import start_site

SITE = Path(__file__).resolve().parents[2] / "test_sites" / "injection"


@pytest.mark.asyncio
async def test_policy_refuses_ssn_and_hidden_instructions(
    sample_profile: CandidateProfile, tmp_path: Path
) -> None:
    server, url = start_site(SITE)
    llm = MockLLMClient(
        FreeTextDraft(
            answer="I wrote the first algorithm at Analytical Engine Co.",
            cited_fact_ids=["exp_001"],
            unsupported=False,
        )
    )
    try:
        async with BrowserManager(profile_dir=tmp_path / "inj", headed=False) as browser:
            await fill_application(
                profile=sample_profile, url=url, llm=llm, browser=browser
            )
            page = browser.context.pages[0]
            assert await page.locator("#ssn").input_value() == ""
            blob = " ".join(
                m["content"] for call in llm.calls for m in call["messages"]
            )
            assert "SSN" not in blob
            assert "ignore previous instructions" not in blob.lower()
    finally:
        server.shutdown()
        server.server_close()
