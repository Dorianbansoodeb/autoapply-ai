from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class JobPosting(BaseModel):
    """Normalized job. Dedupe uses URL + company + title + location + requisition, never title alone."""

    model_config = ConfigDict(extra="forbid")

    company: str
    title: str
    location: str = ""
    description: str
    application_url: str = ""
    requirements: list[str] = Field(default_factory=list)
    job_id: str = ""
    employment_type: str = ""
    salary_min: int | None = None
    salary_max: int | None = None
    ats_type: str = "unknown"
    requisition_id: str = ""
    source: str = "paste"
    discovered_at: str = ""


def load_job(path: Path) -> JobPosting:
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return JobPosting.model_validate(json.loads(raw))
    meta: dict[str, str] = {}
    body: list[str] = []
    for line in raw.splitlines():
        if ":" in line and line.split(":", 1)[0].lower() in {
            "company",
            "title",
            "location",
            "url",
            "application_url",
            "employment_type",
            "ats_type",
            "requisition_id",
            "job_id",
            "source",
        }:
            key, value = line.split(":", 1)
            key = key.strip().lower()
            if key == "url":
                key = "application_url"
            meta[key] = value.strip()
        else:
            body.append(line)
    return JobPosting(
        company=meta.get("company", "Unknown company"),
        title=meta.get("title", "Unknown role"),
        location=meta.get("location", ""),
        application_url=meta.get("application_url", ""),
        employment_type=meta.get("employment_type", ""),
        ats_type=meta.get("ats_type", "unknown"),
        requisition_id=meta.get("requisition_id", ""),
        job_id=meta.get("job_id", ""),
        source=meta.get("source", "paste"),
        description="\n".join(body).strip() or raw,
    )
