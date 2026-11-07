from __future__ import annotations

from pathlib import Path

import pytest

from autoapply.profile import CandidateProfile, load_profile
from test_sites.simple_form.server import start_simple_form

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def sample_profile() -> CandidateProfile:
    return load_profile(FIXTURES / "profile.json")


@pytest.fixture
def resume_path() -> Path:
    return FIXTURES / "resume.txt"


@pytest.fixture
def simple_form_url():
    server, url = start_simple_form()
    try:
        yield url
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def browser_profile_dir(tmp_path: Path) -> Path:
    return tmp_path / "browser-profile"
