# Architecture

The LLM is an untrusted parser and drafter. Deterministic code drives the
browser, checks eligibility, validates documents, and decides what may be
filled. **You click Submit.** Mode C (earned auto-submit) is computed and
logged; this build never sends a Submit click.

```
GUI (PySide6) or CLI
   │  JSON lines (engine process) or direct calls
Engine
   ├─ Profile store          atomic verified facts
   ├─ Job intake             paste, or Greenhouse / Lever / Ashby public JSON
   ├─ Eligibility            hard filters, then an LLM fit explanation
   ├─ Document builder       select, light rewrite, fact validator, PDF + DOCX
   ├─ Form engine            Playwright roles/labels, then a Workday adapter
   ├─ Question engine        classify → answer bank / prefs → draft → flag
   ├─ Policy gate            sensitivity, allowlist, kill switch, daily cap
   └─ SQLite (WAL)           jobs, runs, applications, write-ahead action log
LLM client → OpenAI-compatible localhost only (Ollama default)
```

## State

Jobs move `new → eligible → documents_ready → in_progress → submitted_by_user`,
or into `rejected`, `duplicate`, `expired`, `blocked_by_policy`, `uncertain`,
or `closed`. A run left in `submitting` becomes `uncertain` on the next start
and is not retried.

## What the model is allowed to see

Only the facts retrieved for that question or document, wrapped as untrusted
data when the text came from a page or job posting. Passwords, cookies, and
the full profile are not sent. Secrets are written by the executor into the
browser at fill time.

## Schema changes

`storage/schema.py` creates tables with SQLAlchemy and adds missing columns
in place. That is the migration path for this release. Use Alembic before the
first breaking schema change.
