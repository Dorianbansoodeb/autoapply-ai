"""Hard eligibility filters. Unknown mandatory requirement → not assumed eligible."""

from __future__ import annotations

import re

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
    if re.search(r"bachelor|degree required|must have a degree", blob):
        education = [fact for fact in profile.facts if fact.type == "education"]
        if not education:
            flags.append("degree required and no education fact in profile")
    window = re.search(r"graduat\w+ (?:between|in|by) (\d{4})", blob)
    if window:
        year = window.group(1)
        education = [fact for fact in profile.facts if fact.type == "education"]
        confirmed = any(year in f"{fact.start} {fact.end} {fact.text}" for fact in education)
        if not confirmed:
            flags.append(f"graduation window {year} not confirmed in profile")
    if "internship only" in blob or "students only" in blob:
        titles = " ".join(f"{fact.title or ''} {fact.text}" for fact in profile.facts).lower()
        if "intern" not in titles and "student" not in titles:
            flags.append("internship-only role; no internship or student fact in profile")
    if profile.location and ("must be located" in blob or "onsite only" in blob or "on-site only" in blob):
        loc = profile.location.lower()
        job_loc = job.location.lower()
        if loc not in blob and loc not in job_loc and job_loc not in loc:
            flags.append("location does not match mandatory onsite requirement")
    years = re.search(r"(\d+)\+ years", blob)
    if years:
        needed = int(years.group(1))
        span = _experience_years(profile)
        if span is None:
            flags.append("mandatory experience stated; profile dates unknown — not assumed eligible")
        elif span < needed:
            flags.append(f"mandatory experience {needed}+ years; profile spans about {span}")
    eligible = not flags
    return EligibilityResult(
        eligible=eligible,
        flags=flags,
        estimated_relevance="heuristic only; not a probability",
    )


def _experience_years(profile: CandidateProfile) -> int | None:
    """Rough span from YYYY-MM dates. None when no dated experience exists."""
    starts: list[int] = []
    ends: list[int] = []
    for fact in profile.facts:
        if fact.type != "experience_bullet":
            continue
        start = _year(fact.start)
        end = _year(fact.end) or start
        if start is None:
            continue
        starts.append(start)
        ends.append(end or start)
    if not starts:
        return None
    return max(ends) - min(starts)


def _year(value: str | None) -> int | None:
    if not value:
        return None
    match = re.match(r"(\d{4})", value)
    return int(match.group(1)) if match else None
