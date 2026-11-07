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
            return row

    def record_clean_run(self, url: str) -> SitePolicyRow:
        host = (urlparse(url).hostname or "unknown").lower()
        with Session(self.engine) as session:
            row = session.get(SitePolicyRow, host)
            if row is None:
                row = SitePolicyRow(host=host, mode="B")
                session.add(row)
            row.clean_runs += 1
            if row.clean_runs >= PROMOTE_AFTER and row.allow_auto_submit:
                row.mode = "C"
            session.commit()
            session.refresh(row)
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
            session.commit()
            session.refresh(row)
            return row
