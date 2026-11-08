# Privacy

AutoApply AI is local-first. There is no AutoApply account and no
developer-operated backend.

- Profile facts, jobs, answers, and the action log live in a SQLite file
  under `~/AutoApplyAI/`.
- Tenant passwords live in the operating system keychain (`keyring`). They
  are not written to SQLite, prompts, or ordinary logs.
- The local model receives only the facts needed for one draft, plus the
  question or job text marked as untrusted data. It does not receive
  passwords, session cookies, or the whole profile.
- Job-board fetches go only to public Greenhouse, Lever, and Ashby posting
  APIs, and those requests do not include your profile.
- The browser is a dedicated Playwright profile. The app does not read your
  everyday browser profile and does not read your email.
- `autoapply credentials export` writes passwords to a file you choose so you
  can recover a tenant login. Delete that file when you are done.
- Diagnostic output should be the JSON the CLI already prints. Do not attach
  the keychain export or the SQLite file to a bug report.
