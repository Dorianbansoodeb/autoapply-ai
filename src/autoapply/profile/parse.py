"""LLM extraction of atomic facts. Output is always re-validated in code."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from autoapply.cancel import CancelToken
from autoapply.llm.client import LLMClient, wrap_untrusted
from autoapply.profile.ids import assign_ids
from autoapply.profile.models import CandidateProfile, Fact

EMAIL_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)

FactType = Literal[
    "experience_bullet",
    "education",
    "skill",
    "certification",
]


class ExtractedFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: FactType
    text: str
    employer: str | None = None
    title: str | None = None
    start: str | None = Field(default=None, description="YYYY-MM or YYYY if present")
    end: str | None = None
    technologies: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)


class ResumeExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str
    email: str = ""
    phone: str | None = None
    location: str | None = None
    facts: list[ExtractedFact] = Field(default_factory=list)


SYSTEM_PROMPT = (
    "Extract atomic resume facts. Use only information present in the resume. "
    "Never invent employers, titles, dates, metrics, technologies, degrees, or "
    "contact details. If a field is not in the resume, omit it or use an empty "
    "string. Split experience into one fact per bullet. Return JSON only."
)


def emails_in(text: str) -> list[str]:
    return EMAIL_RE.findall(text)


async def parse_resume(
    source_text: str,
    llm: LLMClient,
    *,
    cancel: CancelToken | None = None,
) -> ResumeExtraction:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": wrap_untrusted(source_text[:12000])},
    ]
    extracted = await llm.complete(messages, ResumeExtraction, cancel=cancel)
    source_emails = emails_in(source_text)
    email = extracted.email.strip()
    if email and email.lower() not in {item.lower() for item in source_emails}:
        email = source_emails[0] if source_emails else ""
    elif not email and source_emails:
        email = source_emails[0]
    name = extracted.full_name.strip()
    if name:
        # Every name token must appear in the resume.
        tokens = [tok for tok in re.split(r"\s+", name) if len(tok) > 1]
        if any(tok.lower() not in source_text.lower() for tok in tokens):
            name = source_text.splitlines()[0][:80]
    else:
        name = source_text.splitlines()[0][:80]
    return extracted.model_copy(update={"full_name": name, "email": email})


def extraction_to_facts(extracted: ResumeExtraction) -> list[Fact]:
    facts: list[Fact] = []
    for item in extracted.facts:
        facts.append(
            Fact(
                id="tmp",
                type=item.type,
                text=item.text.strip(),
                employer=item.employer,
                title=item.title,
                start=item.start,
                end=item.end,
                technologies=item.technologies,
                metrics=item.metrics,
                source="master_resume",
                verified=False,
            )
        )
    return assign_ids([fact for fact in facts if fact.text])


def to_profile(
    extracted: ResumeExtraction,
    facts: list[Fact],
    *,
    resume_path: str | None = None,
) -> CandidateProfile:
    return CandidateProfile(
        full_name=extracted.full_name,
        email=extracted.email,
        phone=extracted.phone,
        location=extracted.location,
        facts=facts,
        resume_path=resume_path,
    )
