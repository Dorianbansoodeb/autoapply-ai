"""Visible kill switch. When on, auto-submit is impossible."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from autoapply.storage.schema import SettingRow, make_engine

KILL_KEY = "kill_switch"


class SettingsStore:
    def __init__(self, db_path: Path, engine=None) -> None:
        self.engine = engine or make_engine(Path(db_path))

    def get(self, key: str, default: str = "") -> str:
        with Session(self.engine) as session:
            row = session.get(SettingRow, key)
            return row.value if row else default

    def set(self, key: str, value: str) -> None:
        with Session(self.engine) as session:
            row = session.get(SettingRow, key)
            if row is None:
                session.add(SettingRow(key=key, value=value))
            else:
                row.value = value
            session.commit()


def kill_switch_on(db_path: Path, engine=None) -> bool:
    return SettingsStore(db_path, engine=engine).get(KILL_KEY, "off") == "on"


def set_kill_switch(db_path: Path, on: bool, engine=None) -> bool:
    SettingsStore(db_path, engine=engine).set(KILL_KEY, "on" if on else "off")
    return on
