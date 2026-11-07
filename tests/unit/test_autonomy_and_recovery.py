from pathlib import Path

from autoapply.jobs.eligibility import check_eligibility
from autoapply.jobs.models import JobPosting
from autoapply.policy.autonomy import can_auto_submit
from autoapply.profile import load_profile
from autoapply.storage.policies import PolicyStore
from autoapply.storage.tracker import Tracker


def test_new_site_cannot_auto_submit(tmp_path: Path) -> None:
    store = PolicyStore(tmp_path / "db.sqlite")
    policy = store.for_url("http://127.0.0.1:9/apply")
    gate = can_auto_submit(
        policy,
        all_required_from_verified=True,
        has_unreviewed_free_text=False,
        has_sensitive_without_saved=False,
        documents_valid=True,
        is_duplicate=False,
        captcha_or_wall=False,
        daily_count=0,
    )
    assert gate.allowed is False
    assert policy.mode == "B"


def test_crash_submitting_becomes_uncertain(tmp_path: Path) -> None:
    tracker = Tracker(tmp_path / "db.sqlite")
    run_id = tracker.start_run("http://127.0.0.1:9/")
    tracker.record_intent("submit", run_id)
    tracker.set_run_state(run_id, "submitting")
    flipped = tracker.recover()
    assert run_id in flipped


def test_eligibility_does_not_assume(fixtures_dir: Path) -> None:
    profile = load_profile(fixtures_dir / "profile.json")
    job = JobPosting(
        company="Bank",
        title="Analyst",
        description="Security clearance required. Must be authorized to work.",
    )
    result = check_eligibility(job, profile)
    assert result.eligible is False
    assert result.flags
