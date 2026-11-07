"""Fill and the LLM client must not open non-localhost network connections."""

from __future__ import annotations

from pathlib import Path

import pytest

from autoapply.browser.manager import BrowserManager
from autoapply.fill import fill_application
from autoapply.llm.client import MockLLMClient, OpenAICompatClient
from autoapply.llm.schemas import FreeTextDraft
from autoapply.profile import CandidateProfile
from autoapply.urls import UrlNotAllowed


@pytest.mark.asyncio
async def test_fill_rejects_chatgpt_as_a_job_site(
    sample_profile: CandidateProfile,
    browser_profile_dir: Path,
) -> None:
    llm = MockLLMClient(
        FreeTextDraft(answer="no", cited_fact_ids=[], unsupported=True)
    )
    async with BrowserManager(profile_dir=browser_profile_dir, headed=False) as browser:
        with pytest.raises(UrlNotAllowed):
            await fill_application(
                profile=sample_profile,
                url="https://chatgpt.com/",
                llm=llm,
                browser=browser,
            )


def test_llm_client_rejects_chatgpt_and_openai() -> None:
    for url in (
        "https://api.openai.com/v1",
        "https://chatgpt.com/",
        "https://cursor.com/",
    ):
        with pytest.raises(UrlNotAllowed):
            OpenAICompatClient(base_url=url)


@pytest.mark.asyncio
async def test_mock_llm_makes_no_http_calls(
    sample_profile: CandidateProfile,
    resume_path: Path,
    simple_form_url: str,
    browser_profile_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_request(*args, **kwargs):
        raise AssertionError("unexpected HTTP request")

    monkeypatch.setattr("httpx.AsyncClient.request", fail_request)
    monkeypatch.setattr("httpx.Client.request", fail_request)

    llm = MockLLMClient(
        FreeTextDraft(
            answer="I wrote the first algorithm at Analytical Engine Co.",
            cited_fact_ids=["exp_001"],
            unsupported=False,
        )
    )
    async with BrowserManager(profile_dir=browser_profile_dir, headed=False) as browser:
        result = await fill_application(
            profile=sample_profile,
            url=simple_form_url,
            llm=llm,
            browser=browser,
            resume_path=resume_path,
        )
    assert result.submit_clicked is False
