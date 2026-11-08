"""LLM fit explanation after deterministic eligibility. Labeled as estimated relevance."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from autoapply.cancel import CancelToken
from autoapply.docs.validate import unsupported_bits
from autoapply.jobs.eligibility import EligibilityResult
from autoapply.jobs.models import JobPosting
from autoapply.llm.client import LLMClient, wrap_untrusted
from autoapply.profile.models import CandidateProfile, Fact


class FitExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    cited_fact_ids: list[str] = Field(default_factory=list)
    estimated_relevance: str = "heuristic only; not a probability"


def _combined(facts: list[Fact]) -> Fact:
    return Fact(
        id="combined",
        type="experience_bullet",
        text=" ".join(fact.text for fact in facts),
        employer=" ".join(fact.employer or "" for fact in facts),
        title=" ".join(fact.title or "" for fact in facts),
        technologies=[tech for fact in facts for tech in fact.technologies],
        metrics=[metric for fact in facts for metric in fact.metrics],
    )


async def explain_fit(
    job: JobPosting,
    profile: CandidateProfile,
    eligibility: EligibilityResult,
    llm: LLMClient,
    *,
    cancel: CancelToken | None = None,
) -> FitExplanation:
    facts = profile.verified_facts() or []
    if not eligibility.eligible:
        reason = "; ".join(eligibility.flags) or "a hard requirement is unknown"
        return FitExplanation(
            summary=f"Not assumed eligible: {reason}.",
            cited_fact_ids=[],
            estimated_relevance="heuristic only; not a probability",
        )
    if not facts:
        return FitExplanation(
            summary="No verified facts to explain fit. Review the profile first.",
            cited_fact_ids=[],
        )
    draft = await llm.complete(
        [
            {
                "role": "system",
                "content": (
                    "Explain why the candidate might fit the job using only the provided facts. "
                    "Do not invent employers, titles, dates, metrics, or technologies. "
                    "This is estimated relevance, not a probability. Return JSON only."
                ),
            },
            {
                "role": "user",
                "content": wrap_untrusted(
                    f"Role: {job.title} at {job.company}\n{job.description}\n\nFacts:\n"
                    + "\n".join(f"- {fact.id}: {fact.text}" for fact in facts)
                ),
            },
        ],
        FitExplanation,
        cancel=cancel,
    )
    known = {fact.id: fact for fact in facts}
    cited = [fact_id for fact_id in draft.cited_fact_ids if fact_id in known]
    source = _combined([known[fact_id] for fact_id in cited] or facts)
    if unsupported_bits(draft.summary, source):
        summary = "Estimated relevance based on verified facts: " + " ".join(
            fact.text for fact in facts[:3]
        )
        return FitExplanation(summary=summary, cited_fact_ids=[fact.id for fact in facts[:3]])
    return FitExplanation(summary=draft.summary, cited_fact_ids=cited)
