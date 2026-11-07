"""Write-ahead action log, form runs, applications. Never auto-retry submit."""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from autoapply.storage.schema import (
    AgentActionRow,
    ApplicationRow,
    FormRunRow,
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

    def start_run(self, url: str, host: str = "127.0.0.1") -> str:
        run_id = new_id()
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
            row.state = state
            if notes:
                row.notes = notes
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
        with Session(self.engine) as session:
            session.add(
                ApplicationRow(
                    id=app_id,
                    company=company,
                    title=title,
                    url=url,
                    state=state,
                    reference=reference,
                )
            )
            session.commit()
        return app_id

    def applications(self) -> list[ApplicationRow]:
        with Session(self.engine) as session:
            return list(session.scalars(select(ApplicationRow)).all())
