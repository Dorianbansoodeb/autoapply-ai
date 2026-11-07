from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class JobPosting(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company: str
    title: str
    location: str = ""
    description: str
    application_url: str = ""
    requirements: list[str] = Field(default_factory=list)


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
        description="\n".join(body).strip() or raw,
    )
