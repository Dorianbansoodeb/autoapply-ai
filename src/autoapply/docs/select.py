"""LLM selects profile fact IDs for a job. Code validates the IDs exist."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from autoapply.cancel import CancelToken
from autoapply.jobs.models import JobPosting
from autoapply.llm.client import LLMClient, wrap_untrusted
from autoapply.profile.models import CandidateProfile, Fact

SYSTEM = (
    "Select the candidate fact IDs that are relevant to the job, most relevant "
    "first. Use only the provided IDs. Never invent facts. Return JSON only."
)


class FactSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fact_ids: list[str] = Field(default_factory=list)


class BulletRewrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fact_id: str
    text: str


class CoverLetterDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paragraphs: list[str] = Field(default_factory=list)
    cited_fact_ids: list[str] = Field(default_factory=list)


def _fact_catalog(facts: list[Fact]) -> str:
    lines = []
    for fact in facts:
        lines.append(
            f"- {fact.id} [{fact.type}] employer={fact.employer} title={fact.title} "
            f"dates={fact.start}..{fact.end} text={fact.text}"
        )
    return "\n".join(lines)


async def select_facts(
    job: JobPosting,
    profile: CandidateProfile,
    llm: LLMClient,
    *,
    cancel: CancelToken | None = None,
) -> list[Fact]:
    facts = profile.verified_facts()
    if not facts:
        raise ValueError("no verified facts; run `autoapply profile verify --all` after review")
    messages = [
        {"role": "system", "content": SYSTEM},
        {
            "role": "user",
            "content": wrap_untrusted(
                f"Job: {job.title} at {job.company}\n{job.description}\n\nFacts:\n{_fact_catalog(facts)}"
            ),
        },
    ]
    selection = await llm.complete(messages, FactSelection, cancel=cancel)
    known = {fact.id: fact for fact in facts}
    ordered: list[Fact] = []
    for fact_id in selection.fact_ids:
        if fact_id in known and known[fact_id] not in ordered:
            ordered.append(known[fact_id])
    return ordered or facts


async def rewrite_bullets(
    job: JobPosting,
    facts: list[Fact],
    llm: LLMClient,
    *,
    cancel: CancelToken | None = None,
) -> dict[str, str]:
    """Optional light rephrase. Validator in the caller falls back to original text."""
    from autoapply.docs.validate import coerce_bullet

    rewrites: dict[str, str] = {fact.id: fact.text for fact in facts}
    for fact in facts:
        if fact.type not in {"experience_bullet", "education"}:
            continue
        messages = [
            {
                "role": "system",
                "content": (
                    "Lightly rephrase this one resume bullet for the target role. "
                    "Do not add numbers, employers, titles, technologies, or dates "
                    "that are not in the source. Return JSON only."
                ),
            },
            {
                "role": "user",
                "content": wrap_untrusted(
                    f"Target: {job.title} at {job.company}\nSource id={fact.id}: {fact.text}"
                ),
            },
        ]
        draft = await llm.complete(
            messages,
            BulletRewrite,
            cancel=cancel,
        )
        rewrites[fact.id] = coerce_bullet(draft.text, fact)
    return rewrites


async def draft_cover_letter(
    job: JobPosting,
    facts: list[Fact],
    profile: CandidateProfile,
    llm: LLMClient,
    *,
    cancel: CancelToken | None = None,
) -> CoverLetterDraft:
    from autoapply.docs.validate import unsupported_bits

    messages = [
        {
            "role": "system",
            "content": (
                "Draft a short cover letter using only the provided facts. "
                "Do not invent employers, titles, dates, or metrics. Return JSON only."
            ),
        },
        {
            "role": "user",
            "content": wrap_untrusted(
                f"Candidate: {profile.full_name}\nRole: {job.title} at {job.company}\n"
                f"Facts:\n{_fact_catalog(facts)}"
            ),
        },
    ]
    draft = await llm.complete(messages, CoverLetterDraft, cancel=cancel)
    known = {fact.id: fact for fact in facts}
    cited = [fid for fid in draft.cited_fact_ids if fid in known]
    paragraphs: list[str] = []
    for para in draft.paragraphs:
        sources = [known[fid] for fid in cited] or facts
        blob = Fact(
            id="combined",
            type="experience_bullet",
            text=" ".join(s.text for s in sources),
            employer=" ".join(s.employer or "" for s in sources),
            title=" ".join(s.title or "" for s in sources),
            technologies=[t for s in sources for t in s.technologies],
            metrics=[m for s in sources for m in s.metrics],
        )
        if unsupported_bits(para, blob):
            continue
        paragraphs.append(para)
    if not paragraphs:
        paragraphs = [
            (
                f"I am applying for {job.title} at {job.company}. "
                + " ".join(fact.text for fact in facts[:3])
            )
        ]
    return CoverLetterDraft(paragraphs=paragraphs, cited_fact_ids=cited)
