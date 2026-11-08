"""Optional PyInstaller build. The supported install path is `uv tool install`.

PyInstaller is GPL with a bootloader exception. It is not a runtime dependency.
Install it only when you are packaging:

    uv run --with pyinstaller python scripts/package_app.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    tool = shutil.which("pyinstaller")
    if tool is None:
        print("pyinstaller is not installed. Use: uv tool install .", file=sys.stderr)
        print("or: uv run --with pyinstaller python scripts/package_app.py", file=sys.stderr)
        return 1
    root = Path(__file__).resolve().parents[1]
    cmd = [
        tool,
        "--name",
        "autoapply",
        "--noconfirm",
        "--clean",
        str(root / "src" / "autoapply" / "__main__.py"),
    ]
    return subprocess.call(cmd, cwd=root)


if __name__ == "__main__":
    raise SystemExit(main())
