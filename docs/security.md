# Security

The threat is a hostile page or job description that tries to talk the model
into pasting secrets, plus a form field that would exfiltrate them. The
defense is code.

- LLM calls are rejected unless the endpoint host is localhost.
- The browser will not open ChatGPT, Cursor, or other inference sites.
- Job JSON is fetched only from Greenhouse, Lever, and Ashby hosts.
- Sensitive and assessment questions are classified in code. EEO-style
  questions default to "Decline to answer" unless you saved an explicit answer.
  Assessments, CAPTCHA, and login walls stop the run and hand you the browser.
- The policy gate refuses SSN, government IDs, bank details, and passwords
  for auto-fill. A generated Workday password is stored in the keychain and
  typed by the executor; the model never sees it.
- File uploads use the resume you passed in or a file the document builder
  wrote under `~/AutoApplyAI/`.
- Web text is wrapped as untrusted data. Hidden fields and page HTML are not
  copied into the prompt.
- The kill switch (`autoapply kill on`, or the button in the GUI) makes
  auto-submit impossible. Unknown sites stay in assisted mode. Workday stays
  assisted even after clean runs.
- A Submit click is never issued by this build. If a run is found in
  `submitting` after a crash, it is marked `uncertain` and left alone.
- Prompt-injection fixtures live in `tests/security/`. The expected result is
  that the gate refuses, not that the model "behaves."
