from pathlib import Path

from autoapply.profile import load_profile


def test_load_sample_profile(fixtures_dir: Path) -> None:
    profile = load_profile(fixtures_dir / "profile.json")
    assert profile.full_name == "Ada Lovelace"
    assert profile.fact_by_id("exp_001") is not None
    assert all(fact.verified for fact in profile.verified_facts())
