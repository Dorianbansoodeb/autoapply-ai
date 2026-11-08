"""Write-ahead action log, form runs, applications. Never auto-retry submit."""

from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from autoapply.jobs.state import FORM_TRANSITIONS, transition
from autoapply.storage.schema import (
    AgentActionRow,
    ApplicationAnswerRow,
    ApplicationDocumentRow,
    ApplicationRow,
    FormRunRow,
    UserInterventionRow,
    make_engine,
)


def new_id() -> str:
    return uuid.uuid4().hex[:12]


class Tracker:
    def __init__(self, db_path: Path, engine=None) -> None:
        self.engine = engine or make_engine(Path(db_path))

    def record_intent(self, intent: str, run_id: str, detail: str = "") -> None:
        """Call *before* any irreversible step."""
        with Session(self.engine) as session:
            session.add(
                AgentActionRow(
                    run_id=run_id, intent=intent, status="recorded", detail=detail
                )
            )
            session.commit()

    def start_run(self, url: str, host: str | None = None) -> str:
        run_id = new_id()
        host = host or (urlparse(url).hostname or "127.0.0.1")
        with Session(self.engine) as session:
            session.add(FormRunRow(id=run_id, url=url, state="opened", host=host))
            session.commit()
        self.record_intent("open", run_id, url)
        return run_id

    def set_run_state(self, run_id: str, state: str, notes: str = "") -> None:
        with Session(self.engine) as session:
            row = session.get(FormRunRow, run_id)
            if row is None:
                return
            row.state = transition(row.state, state, FORM_TRANSITIONS)
            if notes:
                row.notes = notes
            session.commit()

    def note_intervention(self, run_id: str, reason: str) -> None:
        with Session(self.engine) as session:
            session.add(UserInterventionRow(run_id=run_id, reason=reason))
            session.commit()

    def recover(self) -> list[str]:
        """On restart, any run still 'submitting' becomes uncertain. Never retried."""
        flipped: list[str] = []
        with Session(self.engine) as session:
            rows = session.scalars(
                select(FormRunRow).where(FormRunRow.state == "submitting")
            ).all()
            for row in rows:
                row.state = "uncertain"
                row.notes = (row.notes + "\n").strip() + "recovered after crash; not retried"
                flipped.append(row.id)
            session.commit()
        return flipped

    def record_application(
        self,
        *,
        company: str,
        title: str,
        url: str,
        state: str = "submitted_by_user",
        reference: str | None = None,
    ) -> str:
        app_id = new_id()
        self.record_intent("record_application", app_id, url)
        with Session(self.engine) as session:
            session.add(
                ApplicationRow(
                    id=app_id,
                    company=company,
                    title=title,
                    url=url,
                    state=state,
                    reference=reference,
                    created_at=date.today().isoformat(),
                )
            )
            session.commit()
        return app_id

    def add_document(self, application_id: str, kind: str, path: str) -> None:
        with Session(self.engine) as session:
            session.add(ApplicationDocumentRow(application_id=application_id, kind=kind, path=path))
            session.commit()

    def add_answer(
        self, application_id: str, question: str, answer: str, cited_fact_ids: list[str] | None = None
    ) -> None:
        with Session(self.engine) as session:
            session.add(
                ApplicationAnswerRow(
                    application_id=application_id,
                    question=question,
                    answer=answer,
                    cited_fact_ids="\n".join(cited_fact_ids or []),
                )
            )
            session.commit()

    def is_duplicate(self, url: str) -> bool:
        target = (url or "").strip()
        if not target:
            return False
        with Session(self.engine) as session:
            row = session.scalar(
                select(ApplicationRow).where(
                    ApplicationRow.url == target,
                    ApplicationRow.state.in_(("submitted_by_user", "in_progress", "uncertain")),
                )
            )
            return row is not None

    def count_today(self) -> int:
        today = date.today().isoformat()
        with Session(self.engine) as session:
            value = session.scalar(
                select(func.count())
                .select_from(ApplicationRow)
                .where(ApplicationRow.created_at == today)
            )
            return int(value or 0)

    def applications(self) -> list[ApplicationRow]:
        with Session(self.engine) as session:
            rows = list(session.scalars(select(ApplicationRow)).all())
            for row in rows:
                session.expunge(row)
            return rows
