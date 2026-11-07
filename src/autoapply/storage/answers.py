"""Approved answers, reused by question key. Never stores secrets."""

from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from autoapply.storage.schema import AnswerBankRow, make_engine


def normalize_question(question: str) -> str:
    return re.sub(r"\s+", " ", question).strip().lower()


class AnswerBank:
    def __init__(self, db_path: Path, engine=None) -> None:
        self.engine = engine or make_engine(Path(db_path))

    def get(self, question: str) -> AnswerBankRow | None:
        key = normalize_question(question)
        with Session(self.engine) as session:
            return session.scalar(
                select(AnswerBankRow).where(AnswerBankRow.question_key == key)
            )

    def put(
        self,
        question: str,
        answer: str,
        *,
        cited_fact_ids: list[str] | None = None,
        kind: str = "C",
    ) -> None:
        key = normalize_question(question)
        with Session(self.engine) as session:
            row = session.scalar(
                select(AnswerBankRow).where(AnswerBankRow.question_key == key)
            )
            if row is None:
                row = AnswerBankRow(question_key=key)
                session.add(row)
            row.question = question
            row.answer = answer
            row.cited_fact_ids = "\n".join(cited_fact_ids or [])
            row.kind = kind
            row.approved = True
            session.commit()
