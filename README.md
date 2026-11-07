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

## Tests

```bash
uv run pytest
```

## License audit

See [docs/licenses.md](docs/licenses.md). PySide6 is LGPL; keep that notice.
