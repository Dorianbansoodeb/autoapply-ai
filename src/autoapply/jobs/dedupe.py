"""Dedupe on canonical URL + company + title + location + requisition. Never title alone."""

from __future__ import annotations

from urllib.parse import urlparse

from autoapply.jobs.models import JobPosting


def canonical_url(url: str) -> str:
    parsed = urlparse((url or "").strip())
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = (parsed.path or "").rstrip("/").lower()
    return f"{host}{path}"


def dedupe_key(job: JobPosting) -> str:
    requisition = (job.requisition_id or job.job_id or "").strip().lower()
    parts = [
        canonical_url(job.application_url),
        job.company.strip().lower(),
        job.title.strip().lower(),
        job.location.strip().lower(),
        requisition,
    ]
    return "|".join(parts)
