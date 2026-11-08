"""Job rows with dedupe. A second ingest of the same posting is marked duplicate."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from autoapply.jobs.dedupe import dedupe_key
from autoapply.jobs.models import JobPosting
from autoapply.jobs.state import JOB_TRANSITIONS, IllegalTransition, transition
from autoapply.profile.models import today_iso
from autoapply.storage.schema import JobMatchRow, JobRow, make_engine
from autoapply.storage.tracker import new_id


class JobStore:
    def __init__(self, db_path: Path, engine=None) -> None:
        self.engine = engine or make_engine(Path(db_path))

    def add(self, job: JobPosting) -> tuple[JobRow, bool]:
        """Returns (row, created). created is False when this posting was already stored."""
        key = dedupe_key(job)
        with Session(self.engine) as session:
            existing = session.scalar(select(JobRow).where(JobRow.dedupe_key == key))
            if existing is not None:
                session.expunge(existing)
                return existing, False
            row = JobRow(
                id=new_id(),
                dedupe_key=key,
                company=job.company,
                title=job.title,
                location=job.location,
                employment_type=job.employment_type,
                description=job.description,
                requirements="\n".join(job.requirements),
                salary_min=job.salary_min,
                salary_max=job.salary_max,
                application_url=job.application_url,
                ats_type=job.ats_type,
                requisition_id=job.requisition_id or job.job_id,
                source=job.source,
                discovered_at=job.discovered_at or today_iso(),
                state="new",
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            session.expunge(row)
            return row, True

    def set_state(self, job_id: str, state: str) -> None:
        with Session(self.engine) as session:
            row = session.get(JobRow, job_id)
            if row is None:
                raise KeyError(job_id)
            try:
                row.state = transition(row.state, state, JOB_TRANSITIONS)
            except IllegalTransition:
                raise
            session.commit()

    def record_match(self, job_id: str, *, eligible: bool, flags: list[str], relevance: str) -> None:
        with Session(self.engine) as session:
            session.add(
                JobMatchRow(
                    job_id=job_id,
                    eligible=eligible,
                    flags="\n".join(flags),
                    estimated_relevance=relevance,
                )
            )
            session.commit()

    def list_jobs(self) -> list[JobRow]:
        with Session(self.engine) as session:
            rows = list(session.scalars(select(JobRow)).all())
            for row in rows:
                session.expunge(row)
            return rows
