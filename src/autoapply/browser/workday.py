"""Assisted Workday adapter. Mode B only. Never clicks Create Account or Submit."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from playwright.async_api import Page

from autoapply.cancel import CancelToken
from autoapply.llm.client import LLMClient
from autoapply.profile.models import CandidateProfile
from autoapply.questions.engine import answer_question
from autoapply.storage.answers import AnswerBank


async def is_workday(page: Page) -> bool:
    return await page.locator("[data-automation-id]").count() > 0


async def fill_workday(
    page: Page,
    profile: CandidateProfile,
    llm: LLMClient,
    *,
    resume_path: Path | None,
    token: CancelToken,
    state: Any,
    bank: AnswerBank | None = None,
) -> None:
    token.raise_if_cancelled()
    signup = page.locator("[data-automation-id=signupSection]")
    if await signup.count() and await signup.is_visible():
        email = page.locator("#email")
        if await email.count():
            await email.fill(profile.email, force=True)
            state.filled.append("email")
        # Password is generated/stored by the OS keychain in a later hook; never sent to the LLM.
        state.stopped_for_human = True
        state.notes.append(
            "Workday signup: email pre-filled. You click Create Account and the "
            "verification link in your own inbox. The agent does not read email "
            "or click Create Account."
        )
        return

    mapping = [
        ("legalName", profile.full_name, "name"),
        ("contactEmail", profile.email, "email"),
    ]
    for auto_id, value, key in mapping:
        loc = page.locator(f"[data-automation-id='{auto_id}']")
        if await loc.count() and await loc.first.is_visible() and value:
            await loc.first.fill(value)
            state.filled.append(key)

    resume = page.locator("[data-automation-id='resumeUpload']")
    path = Path(resume_path or profile.resume_path or "")
    if await resume.count() and await resume.first.is_visible() and path.is_file():
        await resume.first.set_input_files(str(path))
        state.filled.append("resume")

    cover = page.locator("[data-automation-id='coverQuestion']")
    if await cover.count() and await cover.first.is_visible():
        decision = await answer_question(
            "Why do you want this role?", profile, llm, bank, cancel=token
        )
        if decision.answer:
            await cover.first.fill(decision.answer)
            state.filled.append("cover")
            state.pending_review.append("cover")

    # EEO widgets default to "Decline to answer" in the mock; do not change them.
    next_btns = page.locator("[data-automation-id='bottom-navigation-next-button']")
    for i in range(await next_btns.count()):
        btn = next_btns.nth(i)
        if await btn.is_visible():
            await btn.click()
            await page.wait_for_timeout(150)
            await fill_workday(
                page,
                profile,
                llm,
                resume_path=resume_path,
                token=token,
                state=state,
                bank=bank,
            )
            return
    submit = page.locator("[data-automation-id='bottom-navigation-submit-button']")
    if await submit.count() and await submit.first.is_visible():
        state.notes.append("Workday review: stopped before Submit.")
        return
    state.notes.append("Workday page had no Next/Submit; stopped.")
