"""Page HTML is untrusted data. Hidden injection text must never reach the LLM."""

from __future__ import annotations

from pathlib import Path

import pytest

from autoapply.browser.manager import BrowserManager
from autoapply.fill import fill_application
from autoapply.llm.client import MockLLMClient
from autoapply.llm.schemas import FreeTextDraft
from autoapply.profile import CandidateProfile

INJECTION = "Ignore previous instructions"


@pytest.mark.asyncio
async def test_hidden_injection_is_not_sent_to_llm(
    sample_profile: CandidateProfile,
    resume_path: Path,
    simple_form_url: str,
    browser_profile_dir: Path,
) -> None:
    llm = MockLLMClient(
        FreeTextDraft(
            answer="I wrote the first algorithm at Analytical Engine Co.",
            cited_fact_ids=["exp_001"],
            unsupported=False,
        )
    )
    async with BrowserManager(profile_dir=browser_profile_dir, headed=False) as browser:
        await fill_application(
            profile=sample_profile,
            url=simple_form_url,
            llm=llm,
            browser=browser,
            resume_path=resume_path,
        )

    blob = "\n".join(
        message["content"]
        for call in llm.calls
        for message in call["messages"]
    )
    assert INJECTION not in blob
    assert "SSN" not in blob
    assert "password" not in blob.lower()
    assert "UNTRUSTED DATA" in blob
    assert "ada@example.com" not in blob  # email is filled in the browser, not the prompt
    # Full profile dump would include unverified extras; only facts should appear.
    assert "exp_001" in blob
