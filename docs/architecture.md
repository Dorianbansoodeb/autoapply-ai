# Architecture (Milestone 0 slice)

The LLM is an untrusted parser and drafter. Deterministic code drives the
browser. Milestone 0 proves three things on a local mock ATS:

1. Schema-constrained calls to a local OpenAI-compatible endpoint (Ollama default).
2. Playwright fills known fields from a verified profile.
3. The agent **stops before Submit**.

```
CLI (argparse)
   └── fill_application()
         ├── URL allowlist (localhost only)
         ├── BrowserManager (persistent headed Chromium)
         ├── deterministic fill: name, email, dropdown, file
         └── LLM client: free-text draft into FreeTextDraft schema
```

Not built yet: GUI, SQLite, policy registry UI, ATS adapters, document
builder, question engine, auto-submit.

## Cancellation

A `CancelToken` is checked between steps. In-flight LLM calls close the HTTP
stream. Submit is never clicked, so there is no cancel-and-retry across a
submit.

## Untrusted web content

Only the accessible name of the free-text question is sent to the model,
wrapped as untrusted data. Page HTML, hidden fields, and password inputs are
not.
