from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from autoapply.storage.schema import SitePolicyRow, make_engine

PROMOTE_AFTER = 20


class PolicyStore:
    def __init__(self, db_path: Path, engine=None) -> None:
        self.engine = engine or make_engine(Path(db_path))

    def for_url(self, url: str) -> SitePolicyRow:
        host = (urlparse(url).hostname or "unknown").lower()
        with Session(self.engine) as session:
            row = session.get(SitePolicyRow, host)
            if row is None:
                row = SitePolicyRow(
                    host=host,
                    mode="B",
                    allow_auto_submit=False,
                    notes="unknown policy; assisted only",
                )
                session.add(row)
                session.commit()
                session.refresh(row)
            session.expunge(row)
            return row

    def mark_reviewed(self, url: str) -> SitePolicyRow:
        """User reviewed the site's terms and allowlisted it. Mode stays B until clean runs earn C."""
        host = (urlparse(url).hostname or "unknown").lower()
        with Session(self.engine) as session:
            row = session.get(SitePolicyRow, host)
            if row is None:
                row = SitePolicyRow(host=host, mode="B")
                session.add(row)
            if _workday_host(host):
                row.mode = "B"
                row.allow_auto_submit = False
                row.notes = "Workday stays assisted until the policy registry says otherwise"
            else:
                row.allow_auto_submit = True
                row.mode = "B"
                row.notes = "reviewed; still assisted until clean runs earn auto-submit"
            session.commit()
            session.refresh(row)
            session.expunge(row)
            return row

    def record_clean_run(self, url: str) -> SitePolicyRow:
        host = (urlparse(url).hostname or "unknown").lower()
        with Session(self.engine) as session:
            row = session.get(SitePolicyRow, host)
            if row is None:
                row = SitePolicyRow(host=host, mode="B")
                session.add(row)
            row.clean_runs += 1
            if _workday_host(host):
                row.mode = "B"
                row.allow_auto_submit = False
                row.notes = "Workday stays assisted until the policy registry says otherwise"
            elif row.clean_runs >= PROMOTE_AFTER and row.allow_auto_submit:
                row.mode = "C"
                row.notes = f"promoted after {row.clean_runs} clean runs"
            session.commit()
            session.refresh(row)
            session.expunge(row)
            return row

    def record_failure(self, url: str) -> SitePolicyRow:
        host = (urlparse(url).hostname or "unknown").lower()
        with Session(self.engine) as session:
            row = session.get(SitePolicyRow, host)
            if row is None:
                row = SitePolicyRow(host=host, mode="B")
                session.add(row)
            row.clean_runs = 0
            row.mode = "B"
            row.allow_auto_submit = False
            session.commit()
            session.refresh(row)
            session.expunge(row)
            return row


def _workday_host(host: str) -> bool:
    return "myworkdayjobs.com" in host or host.endswith("workday.com")
