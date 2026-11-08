"""Product-surface checks: jobs, eligibility, policy, tracker, eval size."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from autoapply.cli import main
from autoapply.hardware import detect_hardware
from autoapply.jobs.ats import api_url_for, fetch_posting, parse_lever
from autoapply.jobs.dedupe import dedupe_key
from autoapply.jobs.eligibility import check_eligibility
from autoapply.jobs.fit import FitExplanation, explain_fit
from autoapply.jobs.models import JobPosting
from autoapply.jobs.state import FORM_TRANSITIONS, JOB_TRANSITIONS, IllegalTransition, transition
from autoapply.llm.client import MockLLMClient
from autoapply.policy.autonomy import can_auto_submit
from autoapply.profile import load_profile
from autoapply.storage.jobs import JobStore
from autoapply.storage.policies import PolicyStore
from autoapply.storage.settings import kill_switch_on, set_kill_switch
from autoapply.storage.tracker import Tracker
from autoapply.urls import UrlNotAllowed


def test_dedupe_is_not_title_alone() -> None:
    left = JobPosting(
        company="North",
        title="Engineer",
        description="Build things",
        application_url="https://boards.greenhouse.io/north/jobs/1",
        location="NYC",
    )
    right = JobPosting(
        company="South",
        title="Engineer",
        description="Build things",
        application_url="https://jobs.lever.co/south/abc",
        location="NYC",
    )
    assert dedupe_key(left) != dedupe_key(right)


def test_job_store_marks_second_ingest_duplicate(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "db.sqlite")
    job = JobPosting(
        company="Example Co",
        title="Intern",
        description="Algorithms",
        application_url="https://example.com/jobs/1",
        requisition_id="R1",
    )
    _first, created = store.add(job)
    _again, created_again = store.add(job)
    assert created is True
    assert created_again is False


def test_greenhouse_and_lever_parse_without_network() -> None:
    page = "https://boards.greenhouse.io/acme/jobs/401"
    assert api_url_for(page) == "https://boards-api.greenhouse.io/v1/boards/acme/jobs/401"
    job = fetch_posting(
        page,
        get=lambda _api: {
            "id": 401,
            "title": "Engineer",
            "company_name": "Acme",
            "location": {"name": "NYC"},
            "content": "<p>Build things</p>",
            "absolute_url": page,
            "requisition_id": "R-9",
        },
    )
    assert job.ats_type == "greenhouse"
    assert job.company == "Acme"
    assert "Build things" in job.description
    assert "<p>" not in job.description
    lever = parse_lever(
        {
            "id": "abc",
            "text": "Engineer",
            "categories": {"location": "Remote", "commitment": "Full-time", "team": "Acme"},
            "descriptionPlain": "Write software",
            "hostedUrl": "https://jobs.lever.co/acme/abc",
        }
    )
    assert lever.ats_type == "lever"
    assert lever.employment_type == "Full-time"
    with pytest.raises(UrlNotAllowed):
        api_url_for("https://evil.example/jobs/1")


def test_unknown_degree_and_years_are_not_assumed_eligible(fixtures_dir: Path) -> None:
    profile = load_profile(fixtures_dir / "profile.json")
    job = JobPosting(
        company="Lab",
        title="Researcher",
        description="Bachelor's degree required. 5+ years of experience. Graduating in 2026.",
    )
    result = check_eligibility(job, profile)
    assert result.eligible is False
    blob = " ".join(result.flags)
    assert "degree" in blob
    assert "5+ years" in blob
    assert "2026" in blob


@pytest.mark.asyncio
async def test_fit_explanation_drops_invented_numbers(fixtures_dir: Path) -> None:
    profile = load_profile(fixtures_dir / "profile.json")
    job = JobPosting(company="Example Co", title="Intern", description="Algorithms and writing.")
    llm = MockLLMClient(
        FitExplanation(
            summary="Cut review time by 40% at Analytical Engine Co.",
            cited_fact_ids=["exp_001"],
        )
    )
    from autoapply.jobs.eligibility import EligibilityResult

    fit = await explain_fit(
        job,
        profile,
        EligibilityResult(eligible=True, estimated_relevance="heuristic only; not a probability"),
        llm,
    )
    assert "40" not in fit.summary
    assert "Analytical Engine" in fit.summary


def test_job_and_form_transitions_reject_illegal_jumps() -> None:
    assert transition("new", "eligible", JOB_TRANSITIONS) == "eligible"
    with pytest.raises(IllegalTransition):
        transition("submitted_by_user", "in_progress", JOB_TRANSITIONS)
    assert transition("opened", "submitting", FORM_TRANSITIONS) == "submitting"
    with pytest.raises(IllegalTransition):
        transition("uncertain", "submitting", FORM_TRANSITIONS)


def test_workday_never_promotes_and_kill_switch_blocks(tmp_path: Path) -> None:
    db = tmp_path / "db.sqlite"
    store = PolicyStore(db)
    workday = "https://acme.wd5.myworkdayjobs.com/en-US/External/job/1"
    store.mark_reviewed(workday)
    row = store.for_url(workday)
    for _ in range(20):
        row = store.record_clean_run(workday)
    assert row.mode == "B"
    assert row.allow_auto_submit is False

    greenhouse = "https://boards.greenhouse.io/acme/jobs/1"
    store.mark_reviewed(greenhouse)
    for _ in range(20):
        row = store.record_clean_run(greenhouse)
    assert row.mode == "C"

    set_kill_switch(db, True)
    assert kill_switch_on(db) is True
    gate = can_auto_submit(
        row,
        all_required_from_verified=True,
        has_unreviewed_free_text=False,
        has_sensitive_without_saved=False,
        documents_valid=True,
        is_duplicate=False,
        captcha_or_wall=False,
        daily_count=0,
        kill_switch=True,
    )
    assert gate.allowed is False
    assert any("kill switch" in reason for reason in gate.reasons)


def test_record_is_duplicate_and_crash_does_not_resubmit(tmp_path: Path) -> None:
    tracker = Tracker(tmp_path / "db.sqlite")
    url = "http://127.0.0.1:9/apply"
    first = tracker.record_application(company="Acme", title="Intern", url=url, reference="A-1")
    assert tracker.is_duplicate(url) is True
    assert tracker.count_today() == 1
    assert first
    run_id = tracker.start_run(url)
    tracker.record_intent("submit", run_id)
    tracker.set_run_state(run_id, "submitting")
    flipped = tracker.recover()
    assert run_id in flipped
    assert len(tracker.applications()) == 1


def test_doctor_and_job_add_cli(tmp_path: Path, fixtures_dir: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["doctor"])
    assert exc.value.code == 0
    db = tmp_path / "db.sqlite"
    with pytest.raises(SystemExit) as added:
        main(["job", "add", str(fixtures_dir / "job.txt"), "--db", str(db)])
    assert added.value.code == 0
    with pytest.raises(SystemExit) as again:
        main(["job", "add", str(fixtures_dir / "job.txt"), "--db", str(db)])
    assert again.value.code == 0
    rows = JobStore(db).list_jobs()
    assert len(rows) == 1
    report = detect_hardware()
    assert report.tier in {"limited", "practical", "comfortable", "unknown"}
    assert report.os


def test_eval_set_has_two_hundred_items() -> None:
    path = Path(__file__).resolve().parents[1] / "fixtures" / "eval_set.json"
    items = json.loads(path.read_text(encoding="utf-8"))
    assert len(items) >= 200


def test_gui_window_opens_offscreen(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    monkeypatch.setattr(QApplication, "exec", lambda self: 0)
    monkeypatch.setattr("autoapply.engine.protocol.Engine.__init__", lambda self: None)
    with pytest.raises(SystemExit) as exc:
        main(["gui"])
    assert exc.value.code == 0
