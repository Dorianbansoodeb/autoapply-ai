"""Local data directories. File access stays under ~/AutoApplyAI/."""

from __future__ import annotations

from pathlib import Path

DATA_ROOT = Path.home() / "AutoApplyAI"
PROFILE_DIR = DATA_ROOT / "profile"
DOCUMENTS_DIR = DATA_ROOT / "documents"
APPLICATIONS_DIR = DATA_ROOT / "applications"
DEFAULT_DB_PATH = DATA_ROOT / "autoapply.db"
DEFAULT_JSON_PATH = PROFILE_DIR / "profile.json"


def ensure_data_dirs(root: Path | None = None) -> Path:
    base = root or DATA_ROOT
    for child in ("profile", "documents", "applications"):
        (base / child).mkdir(parents=True, exist_ok=True)
    return base
