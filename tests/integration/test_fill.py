from __future__ import annotations

from pathlib import Path

import pytest

from autoapply.browser.manager import BrowserManager
from autoapply.fill import fill_application
from autoapply.llm.client import MockLLMClient
from autoapply.llm.schemas import FreeTextDraft
from autoapply.profile import CandidateProfile


def _mock_llm() -> MockLLMClient:
    return MockLLMClient(
        FreeTextDraft(
            answer="I want this role because I wrote the first algorithm at Analytical Engine Co.",
            cited_fact_ids=["exp_001"],
            unsupported=False,
        )
    )


@pytest.mark.asyncio
async def test_fills_deterministic_fields_and_stops_before_submit(
    sample_profile: CandidateProfile,
    resume_path: Path,
    simple_form_url: str,
    browser_profile_dir: Path,
) -> None:
    llm = _mock_llm()
    async with BrowserManager(profile_dir=browser_profile_dir, headed=False) as browser:
        result = await fill_application(
            profile=sample_profile,
            url=simple_form_url,
            llm=llm,
            browser=browser,
            resume_path=resume_path,
        )
        page = browser.context.pages[0]
        assert await page.get_by_label("Full name").input_value() == "Ada Lovelace"
        assert await page.get_by_label("Email").input_value() == "ada@example.com"
        assert await page.get_by_label("Work authorization").input_value() == "yes"
        cover = await page.get_by_label("Why do you want this role?").input_value()
        assert "Analytical Engine Co" in cover
        assert await page.get_by_role("button", name="Submit application").count() == 1
        assert await page.get_by_role("heading", name="Application received").count() == 0
        secret = await page.locator("#secret").input_value()
        assert secret == ""

    assert result.submit_clicked is False
    assert result.confirmation_visible is False
    assert result.status == "ready_for_review"
    assert "cover" in result.pending_review
    assert "name" in result.filled_fields
    assert llm.calls, "LLM should be asked only for the free-text question"
    prompt = llm.calls[0]["messages"][1]["content"]
    assert "Why do you want this role?" in prompt
    assert "exp_001" in prompt


def test_cli_fill_headless(
    tmp_path: Path,
    sample_profile: CandidateProfile,
    resume_path: Path,
    simple_form_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CLI wiring: argparse → fill, headless so it does not wait on stdin."""
    from autoapply.cli import main
    from autoapply.llm.client import MockLLMClient as _Mock
    from autoapply.llm.schemas import FreeTextDraft as _Draft

    profile_path = tmp_path / "profile.json"
    profile_path.write_text(sample_profile.model_dump_json(), encoding="utf-8")
    browser_dir = tmp_path / "bp"

    mock = _Mock(
        _Draft(
            answer="Draft from CLI test.",
            cited_fact_ids=["exp_001"],
            unsupported=False,
        )
    )

    class _FakeOpenAI:
        def __init__(self, *args, **kwargs):
            pass

        async def complete(self, *args, **kwargs):
            return await mock.complete(*args, **kwargs)

        async def aclose(self):
            return None

    monkeypatch.setattr("autoapply.cli.OpenAICompatClient", _FakeOpenAI)
    with pytest.raises(SystemExit) as exc:
        main(
            [
                "fill",
                "--profile",
                str(profile_path),
                "--url",
                simple_form_url,
                "--resume",
                str(resume_path),
                "--headless",
                "--browser-profile",
                str(browser_dir),
            ]
        )
    assert exc.value.code == 0
