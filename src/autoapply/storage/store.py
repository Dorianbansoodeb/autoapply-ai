"""SQLite (WAL) profile store. Secrets never go here."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from autoapply.profile.models import CandidateProfile, Fact, dump_profile
from autoapply.storage.schema import CandidateRow, FactRow, make_engine


def _split(value: str) -> list[str]:
    return [part for part in value.split("\n") if part]


def _join(values: list[str]) -> str:
    return "\n".join(values)


class ProfileStore:
    def __init__(self, db_path: Path, engine=None) -> None:
        self.db_path = Path(db_path)
        self.engine = engine or make_engine(self.db_path)

    def save(self, profile: CandidateProfile) -> None:
        with Session(self.engine) as session:
            row = session.get(CandidateRow, profile.id)
            if row is None:
                row = CandidateRow(id=profile.id)
                session.add(row)
            row.full_name = profile.full_name
            row.email = profile.email
            row.phone = profile.phone
            row.location = profile.location
            row.work_authorization = profile.work_authorization
            row.resume_path = profile.resume_path
            session.flush()
            session.execute(delete(FactRow).where(FactRow.candidate_id == profile.id))
            session.flush()
            for fact in profile.facts:
                row.facts.append(
                    FactRow(
                        id=fact.id,
                        candidate_id=profile.id,
                        type=fact.type,
                        text=fact.text,
                        employer=fact.employer,
                        title=fact.title,
                        start=fact.start,
                        end=fact.end,
                        technologies=_join(fact.technologies),
                        metrics=_join(fact.metrics),
                        source=fact.source,
                        verified=fact.verified,
                        last_confirmed=fact.last_confirmed,
                    )
                )
            session.commit()

    def load(self, candidate_id: str = "default") -> CandidateProfile | None:
        with Session(self.engine) as session:
            row = session.get(CandidateRow, candidate_id)
            if row is None:
                row = session.scalar(select(CandidateRow).limit(1))
            if row is None:
                return None
            facts = [
                Fact(
                    id=fact.id,
                    type=fact.type,
                    text=fact.text,
                    employer=fact.employer,
                    title=fact.title,
                    start=fact.start,
                    end=fact.end,
                    technologies=_split(fact.technologies),
                    metrics=_split(fact.metrics),
                    source=fact.source,
                    verified=fact.verified,
                    last_confirmed=fact.last_confirmed,
                )
                for fact in row.facts
            ]
            return CandidateProfile(
                id=row.id,
                full_name=row.full_name,
                email=row.email,
                phone=row.phone,
                location=row.location,
                work_authorization=row.work_authorization,
                facts=facts,
                resume_path=row.resume_path,
            )

    def export_json(self, path: Path, candidate_id: str = "default") -> Path:
        profile = self.load(candidate_id)
        if profile is None:
            raise FileNotFoundError("no profile stored yet")
        dump_profile(profile, path)
        return path
