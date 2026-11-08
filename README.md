# AutoApply AI

Local-first job application assistant. A local LLM drafts text; deterministic
Playwright code drives the browser. **You click Submit.** Auto-submit stays off
until a site earns it (none start earned).

## Setup

```bash
source "$HOME/.local/bin/env"   # if uv/ollama are not on PATH
cd ~/Projects/autoapply-ai
uv sync --group dev
uv run playwright install chromium
```

Ollama should be running at `127.0.0.1:11434`.

## Run

**GUI**

```bash
uv run autoapply gui
```

Assisted fill works on a job URL you paste (`autoapply fill --url …`). The
model still runs only on localhost. ChatGPT/Cursor are blocked. **You click
Submit.** Real ATS pages vary; CAPTCHA/login/assessments hand control back to you.

**CLI demo (mock form)**

```bash
uv run python test_sites/simple_form/server.py --port 8765
uv run autoapply fill --profile tests/fixtures/profile.json --url http://127.0.0.1:8765/ --resume tests/fixtures/resume.txt
```

**Profile → documents**

```bash
uv run autoapply profile import tests/fixtures/ada_resume.txt
uv run autoapply profile verify --all
uv run autoapply docs build --job tests/fixtures/job.txt --profile ~/AutoApplyAI/profile/profile.json --out /tmp/autoapply-docs
```

After a crash: `uv run autoapply recover` marks any `submitting` run as `uncertain` and does not retry.

**Jobs, tracker, kill switch**

```bash
uv run autoapply doctor
uv run autoapply job add tests/fixtures/job.txt
uv run autoapply job fetch https://boards.greenhouse.io/BOARD/jobs/ID
uv run autoapply record --company "Example Co" --title "Intern" --url https://example.com/apply
uv run autoapply applications
uv run autoapply kill on
uv run autoapply policy show https://boards.greenhouse.io/example/jobs/1
uv run autoapply credentials list
```

Greenhouse, Lever, and Ashby fetches use those vendors' public posting APIs.
Workday stays assisted: the adapter prefills email and a keychain password,
then you click Create Account. This build never clicks Submit. Mode C is
only a gate result until a site has been reviewed and has 20 clean runs, and
even then the browser does not auto-submit.

Install for daily use: `uv tool install .` from a checkout. A PyInstaller
bundle is optional (`python scripts/package_app.py`) and is not required to
run the app.

## Tests

```bash
uv run pytest
```

## License audit

See [docs/licenses.md](docs/licenses.md). PySide6 is LGPL; keep that notice.

Also see [docs/architecture.md](docs/architecture.md), [docs/privacy.md](docs/privacy.md), [docs/security.md](docs/security.md), and [docs/site-compliance.md](docs/site-compliance.md).
