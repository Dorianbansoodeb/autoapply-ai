"""Hard eligibility filters. Unknown mandatory requirement → not assumed eligible."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from autoapply.jobs.models import JobPosting
from autoapply.profile.models import CandidateProfile


class EligibilityResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    eligible: bool
    flags: list[str] = Field(default_factory=list)
    estimated_relevance: str = "unknown"


def check_eligibility(job: JobPosting, profile: CandidateProfile) -> EligibilityResult:
    flags: list[str] = []
    blob = f"{job.description} {' '.join(job.requirements)}".lower()
    auth = profile.work_authorization.lower()
    if "must be authorized" in blob or "work authorization required" in blob:
        if auth not in {"authorized", "yes"}:
            flags.append("work authorization unknown or missing")
    if "security clearance required" in blob:
        flags.append("mandatory clearance; not in profile — not assumed eligible")
    if "required certification" in blob or "must have certification" in blob:
        certs = " ".join(
            f.text.lower() for f in profile.facts if f.type == "certification"
        )
        if not certs:
            flags.append("mandatory certification not found in profile")
    eligible = not flags
    return EligibilityResult(
        eligible=eligible,
        flags=flags,
        estimated_relevance="heuristic only; not a probability",
    )
