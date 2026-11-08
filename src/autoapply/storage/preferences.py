"""Saved preferences. Asked once, then reused. Never inferred."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from autoapply.storage.schema import PreferenceRow, make_engine


class PreferenceStore:
    def __init__(self, db_path: Path, engine=None) -> None:
        self.engine = engine or make_engine(Path(db_path))

    def get(self, key: str) -> str | None:
        with Session(self.engine) as session:
            row = session.get(PreferenceRow, key.strip().lower())
            return row.value if row else None

    def set(self, key: str, value: str) -> None:
        name = key.strip().lower()
        with Session(self.engine) as session:
            row = session.get(PreferenceRow, name)
            if row is None:
                row = PreferenceRow(key=name, value=value)
                session.add(row)
            else:
                row.value = value
            session.commit()

    def as_dict(self) -> dict[str, str]:
        with Session(self.engine) as session:
            rows = session.scalars(select(PreferenceRow)).all()
            return {row.key: row.value for row in rows}
