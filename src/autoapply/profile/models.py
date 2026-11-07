"""In-memory atomic profile. Each fact has an ID so documents can cite it."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class Fact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: str
    text: str
    employer: str | None = None
    title: str | None = None
    start: str | None = None
    end: str | None = None
    technologies: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    source: str = "master_resume"
    verified: bool = False
    last_confirmed: str | None = None


class CandidateProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = "default"
    full_name: str
    email: str
    phone: str | None = None
    location: str | None = None
    work_authorization: str = "unknown"
    facts: list[Fact] = Field(default_factory=list)
    resume_path: str | None = None

    def fact_by_id(self, fact_id: str) -> Fact | None:
        for fact in self.facts:
            if fact.id == fact_id:
                return fact
        return None

    def verified_facts(self) -> list[Fact]:
        return [fact for fact in self.facts if fact.verified]


def load_profile(path: Path) -> CandidateProfile:
    data = json.loads(path.read_text(encoding="utf-8"))
    return CandidateProfile.model_validate(data)


def dump_profile(profile: CandidateProfile, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(profile.model_dump_json(indent=2) + "\n", encoding="utf-8")


def today_iso() -> str:
    return date.today().isoformat()
