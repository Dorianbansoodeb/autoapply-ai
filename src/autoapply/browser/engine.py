"""Deterministic form filler. LLM is only used for free-text questions.

Never clicks Submit. Never fills passwords, SSN, or EEO/sensitive fields.
"""

from __future__ import annotations

import re
from pathlib import Path

from playwright.async_api import Frame, Page

from autoapply.cancel import CancelToken, CancelledError
from autoapply.llm.client import LLMClient
from autoapply.llm.schemas import FreeTextDraft
from autoapply.policy.gate import may_auto_fill, page_looks_like_assessment
from autoapply.profile.models import CandidateProfile
from autoapply.browser.workday import fill_workday, is_workday
from autoapply.questions.engine import answer_question
from autoapply.storage.answers import AnswerBank

WORK_AUTH_OPTIONS = {
    "authorized": "Authorized to work",
    "yes": "Authorized to work",
    "not_authorized": "Not authorized",
    "no": "Not authorized",
}

SKIP_RE = re.compile(
    r"password|ssn|social.?security|disability|veteran|gender|race|hispanic|"
    r"ethnicity|criminal|immigration",
    re.I,
)
NAME_RE = re.compile(r"^(full )?name$|legal name", re.I)
EMAIL_RE = re.compile(r"e-?mail", re.I)
PHONE_RE = re.compile(r"phone|mobile|tel", re.I)
RESUME_RE = re.compile(r"resume|cv|curriculum", re.I)
AUTH_RE = re.compile(r"work authori|authorized to work", re.I)
COVER_RE = re.compile(r"why do you want|cover letter|additional (info|information)", re.I)
CERTIFY_RE = re.compile(r"i certify|information is (true|accurate)|i agree that the information", re.I)
NEXT_RE = re.compile(r"^(next|continue)$", re.I)
SUBMIT_RE = re.compile(r"submit", re.I)
CAPTCHA_RE = re.compile(r"captcha|i.?m not a robot|verify you are human", re.I)

SYSTEM_PROMPT = (
    "You draft a short job-application answer. Use only the provided candidate "
    "facts. Never invent employers, titles, dates, metrics, or technologies. "
    "If the question cannot be answered from those facts, set unsupported=true "
    "and say so in the answer. Cite fact IDs you used. Return JSON only."
)


class FillState:
    def __init__(self) -> None:
        self.filled: list[str] = []
        self.pending_review: list[str] = []
        self.notes: list[str] = []
        self.draft: FreeTextDraft | None = None
        self.stopped_for_human: bool = False


async def fill_page(
    page: Page,
    profile: CandidateProfile,
    llm: LLMClient,
    *,
    resume_path: Path | None,
    token: CancelToken,
    state: FillState,
    max_pages: int = 8,
    bank: AnswerBank | None = None,
    saved_prefs: dict[str, str] | None = None,
) -> None:
    for _ in range(max_pages):
        token.raise_if_cancelled()
        body = ""
        try:
            body = await page.inner_text("body")
        except Exception:
            body = ""
        if page_looks_like_assessment(body) or CAPTCHA_RE.search(body):
            state.stopped_for_human = True
            state.notes.append(
                "CAPTCHA, MFA, or assessment detected; handing control to you."
            )
            return
        if await is_workday(page):
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
        for frame in page.frames:
            await _fill_frame(
                frame, profile, llm, resume_path, token, state, bank=bank, saved_prefs=saved_prefs
            )
        if await _error_visible(page):
            for frame in page.frames:
                await _fill_frame(
                    frame,
                    profile,
                    llm,
                    resume_path,
                    token,
                    state,
                    bank=bank,
                    saved_prefs=saved_prefs,
                )
        next_btn = page.get_by_role("button", name=NEXT_RE)
        submit = page.get_by_role("button", name=SUBMIT_RE)
        if await next_btn.count() and await next_btn.first.is_visible():
            await next_btn.first.click()
            await page.wait_for_timeout(150)
            continue
        if await submit.count():
            state.notes.append("Stopped before Submit. Review the draft, then submit yourself.")
            return
        state.notes.append("No Submit button found")
        return


async def _fill_frame(
    frame: Frame,
    profile: CandidateProfile,
    llm: LLMClient,
    resume_path: Path | None,
    token: CancelToken,
    state: FillState,
    bank: AnswerBank | None = None,
    saved_prefs: dict[str, str] | None = None,
) -> None:
    labels = await _labels(frame)
    for label in labels:
        token.raise_if_cancelled()
        if SKIP_RE.search(label) or not may_auto_fill(label):
            state.notes.append(f"Skipped sensitive or assessment field: {label}")
            continue
        control = frame.get_by_label(label, exact=True)
        if await control.count() == 0:
            continue
        target = control.first
        if not await target.is_visible():
            continue
        kind = await _kind(target)
        if kind in {"password", "hidden"}:
            continue
        if NAME_RE.search(label):
            await target.fill(profile.full_name)
            state.filled.append("name")
        elif EMAIL_RE.search(label):
            await target.fill(profile.email)
            state.filled.append("email")
        elif PHONE_RE.search(label) and profile.phone:
            await target.fill(profile.phone)
            state.filled.append("phone")
        elif RESUME_RE.search(label) and kind == "file":
            path = Path(resume_path or profile.resume_path or "")
            if path.is_file():
                await target.set_input_files(str(path))
                state.filled.append("resume")
        elif AUTH_RE.search(label):
            await _fill_choice(frame, target, label, profile, state)
        elif CERTIFY_RE.search(label) and kind in {"checkbox", "unknown"}:
            await target.check()
            state.filled.append("certify")
        elif COVER_RE.search(label) or kind == "textarea":
            await _fill_textarea(
                target, label, profile, llm, token, state, bank, saved_prefs=saved_prefs
            )


async def _fill_choice(frame: Frame, target, label: str, profile: CandidateProfile, state: FillState) -> None:
    wanted = WORK_AUTH_OPTIONS.get(profile.work_authorization.lower())
    if not wanted:
        state.notes.append("Work authorization not mapped; left unfilled")
        return
    try:
        await target.select_option(label=wanted)
        state.filled.append("work_authorization")
        return
    except Exception:
        pass
    try:
        await target.click()
        option = frame.get_by_role("option", name=wanted)
        await option.click()
        state.filled.append("work_authorization")
    except Exception as exc:  # noqa: BLE001
        state.notes.append(f"Could not set work authorization: {exc}")


async def _fill_textarea(target, label, profile, llm, token, state, bank, saved_prefs=None) -> None:
    try:
        decision = await answer_question(
            label, profile, llm, bank, cancel=token, saved_prefs=saved_prefs
        )
    except CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001
        state.notes.append(f"Free-text draft failed: {exc}")
        return
    if decision.action == "stop":
        state.stopped_for_human = True
        state.notes.append(decision.reason)
        return
    if decision.action == "ask":
        state.notes.append(decision.reason)
        state.pending_review.append(label)
        return
    if decision.answer:
        await target.fill(decision.answer)
        state.filled.append("cover")
        if decision.needs_review:
            state.pending_review.append("cover")
        state.draft = FreeTextDraft(
            answer=decision.answer,
            cited_fact_ids=decision.cited_fact_ids,
            unsupported=decision.unsupported,
        )
    state.notes.append(decision.reason)


async def _labels(frame: Frame) -> list[str]:
    return await frame.locator("label").evaluate_all(
        "els => els.map(e => (e.innerText || e.textContent || '').trim()).filter(Boolean)"
    )


async def _kind(locator) -> str:
    try:
        input_type = await locator.get_attribute("type")
        tag = await locator.evaluate("el => el.tagName.toLowerCase()")
    except Exception:
        return "unknown"
    if input_type:
        return input_type.lower()
    return tag or "unknown"


async def _error_visible(page: Page) -> bool:
    alert = page.get_by_role("alert")
    return await alert.count() > 0 and await alert.first.is_visible()
