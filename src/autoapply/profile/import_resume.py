"""Import a resume into unverified atomic facts. User must verify."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from autoapply.cancel import CancelToken
from autoapply.llm.client import LLMClient
from autoapply.profile.extract import extract_text
from autoapply.profile.models import CandidateProfile, Fact
from autoapply.profile.parse import extraction_to_facts, parse_resume, to_profile
from autoapply.profile.validate import filter_facts


class ImportResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: CandidateProfile
    source_text: str
    kept: int
    rejected: list[dict] = Field(default_factory=list)


async def import_resume(
    path: Path,
    llm: LLMClient,
    *,
    cancel: CancelToken | None = None,
) -> ImportResult:
    source_text = extract_text(path)
    extracted = await parse_resume(source_text, llm, cancel=cancel)
    facts = extraction_to_facts(extracted)
    kept_facts, rejected = filter_facts(facts, source_text)
    profile = to_profile(extracted, kept_facts, resume_path=str(path.resolve()))
    return ImportResult(
        profile=profile,
        source_text=source_text,
        kept=len(kept_facts),
        rejected=[
            {"id": fact.id, "text": fact.text, "reasons": reasons}
            for fact, reasons in rejected
        ],
    )


def verify_facts(profile: CandidateProfile, fact_ids: list[str] | None, when: str) -> CandidateProfile:
    ids = set(fact_ids) if fact_ids is not None else {fact.id for fact in profile.facts}
    updated: list[Fact] = []
    for fact in profile.facts:
        if fact.id in ids:
            updated.append(fact.model_copy(update={"verified": True, "last_confirmed": when}))
        else:
            updated.append(fact)
    return profile.model_copy(update={"facts": updated})
