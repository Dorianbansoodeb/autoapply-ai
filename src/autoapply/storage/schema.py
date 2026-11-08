"""SQLite schema. Secrets never live here."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, Session


class Base(DeclarativeBase):
    pass


class CandidateRow(Base):
    __tablename__ = "candidates"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(256))
    email: Mapped[str] = mapped_column(String(256))
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    location: Mapped[str | None] = mapped_column(String(256), nullable=True)
    work_authorization: Mapped[str] = mapped_column(String(64), default="unknown")
    resume_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    facts: Mapped[list[FactRow]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )


class FactRow(Base):
    __tablename__ = "candidate_facts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id"))
    type: Mapped[str] = mapped_column(String(64))
    text: Mapped[str] = mapped_column(Text)
    employer: Mapped[str | None] = mapped_column(String(256), nullable=True)
    title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    start: Mapped[str | None] = mapped_column(String(32), nullable=True)
    end: Mapped[str | None] = mapped_column(String(32), nullable=True)
    technologies: Mapped[str] = mapped_column(Text, default="")
    metrics: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(64), default="master_resume")
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    last_confirmed: Mapped[str | None] = mapped_column(String(32), nullable=True)
    candidate: Mapped[CandidateRow] = relationship(back_populates="facts")


class AnswerBankRow(Base):
    __tablename__ = "answer_bank"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question_key: Mapped[str] = mapped_column(String(512), unique=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    cited_fact_ids: Mapped[str] = mapped_column(Text, default="")
    kind: Mapped[str] = mapped_column(String(8), default="C")
    approved: Mapped[bool] = mapped_column(Boolean, default=True)


class SitePolicyRow(Base):
    __tablename__ = "site_policies"

    host: Mapped[str] = mapped_column(String(256), primary_key=True)
    mode: Mapped[str] = mapped_column(String(8), default="B")  # A prep, B assisted, C auto
    clean_runs: Mapped[int] = mapped_column(Integer, default=0)
    allow_auto_submit: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str] = mapped_column(Text, default="unknown policy; assisted only")


class FormRunRow(Base):
    __tablename__ = "form_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    url: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(32), default="opened")
    host: Mapped[str] = mapped_column(String(256), default="127.0.0.1")
    notes: Mapped[str] = mapped_column(Text, default="")


class ApplicationRow(Base):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    company: Mapped[str] = mapped_column(String(256), default="")
    title: Mapped[str] = mapped_column(String(256), default="")
    url: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(32), default="in_progress")
    reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), default="")


class JobRow(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dedupe_key: Mapped[str] = mapped_column(String(512), unique=True)
    company: Mapped[str] = mapped_column(String(256))
    title: Mapped[str] = mapped_column(String(256))
    location: Mapped[str] = mapped_column(String(256), default="")
    employment_type: Mapped[str] = mapped_column(String(64), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    requirements: Mapped[str] = mapped_column(Text, default="")
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    application_url: Mapped[str] = mapped_column(Text, default="")
    ats_type: Mapped[str] = mapped_column(String(32), default="unknown")
    requisition_id: Mapped[str] = mapped_column(String(128), default="")
    source: Mapped[str] = mapped_column(String(64), default="paste")
    discovered_at: Mapped[str] = mapped_column(String(32), default="")
    state: Mapped[str] = mapped_column(String(32), default="new")


class JobMatchRow(Base):
    __tablename__ = "job_matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(64))
    eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    flags: Mapped[str] = mapped_column(Text, default="")
    estimated_relevance: Mapped[str] = mapped_column(Text, default="")


class ApplicationDocumentRow(Base):
    __tablename__ = "application_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(32))
    path: Mapped[str] = mapped_column(Text)


class ApplicationAnswerRow(Base):
    __tablename__ = "application_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[str] = mapped_column(String(64))
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    cited_fact_ids: Mapped[str] = mapped_column(Text, default="")


class PreferenceRow(Base):
    __tablename__ = "candidate_preferences"

    key: Mapped[str] = mapped_column(String(256), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


class UserInterventionRow(Base):
    __tablename__ = "user_interventions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), default="")
    reason: Mapped[str] = mapped_column(Text, default="")


class SettingRow(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class AgentActionRow(Base):
    __tablename__ = "agent_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), default="")
    intent: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="recorded")
    detail: Mapped[str] = mapped_column(Text, default="")


def make_engine(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
        conn.commit()
    Base.metadata.create_all(engine)
    _ensure_columns(engine)
    return engine


def _ensure_columns(engine) -> None:
    """Additive columns for databases created before a field existed."""
    with engine.connect() as conn:
        rows = conn.execute(text("PRAGMA table_info(applications)")).fetchall()
        names = {row[1] for row in rows}
        if rows and "created_at" not in names:
            conn.execute(text("ALTER TABLE applications ADD COLUMN created_at TEXT DEFAULT ''"))
            conn.commit()


def session_for(engine) -> Session:
    return Session(engine)
