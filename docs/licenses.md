# Dependency license audit (Milestone 0)

Run this audit again before adding any dependency. Do not add a package until
the license is checked and recorded here.

Weights are **not** redistributed. Users pull models from the official Ollama
registry after seeing a size estimate.

## Runtime (Python)

| Package    | License        | Notes                                      |
|------------|----------------|--------------------------------------------|
| httpx      | BSD-3-Clause   | Local HTTP client for Ollama / llama.cpp   |
| pydantic   | MIT            | Schema validation of model output          |
| playwright | Apache-2.0     | Headed Chromium; dedicated profile only    |
| pypdf      | BSD-3-Clause   | Resume PDF text extraction (not PyMuPDF)   |
| python-docx| MIT            | Resume DOCX text extraction; later output  |
| sqlalchemy | MIT            | SQLite WAL profile store                   |
| keyring    | MIT            | OS keychain for tenant passwords           |
| PySide6    | LGPL-3.0       | Desktop UI; keep license notices           |

## Dev / test

| Package         | License        | Notes                |
|-----------------|----------------|----------------------|
| pytest          | MIT            |                      |
| pytest-asyncio  | Apache-2.0     |                      |
| hatchling       | MIT            | Build backend        |

## Local toolchain (not Python packages)

| Tool     | License | Notes                                                                 |
|----------|---------|-----------------------------------------------------------------------|
| Ollama   | MIT     | Optional. Official darwin binary from GitHub releases.                |
| uv       | Apache-2.0 / MIT | Package manager.                                             |
| Chromium (Playwright) | BSD-style | Downloaded by `playwright install chromium`. Not a model. |

## Models (user-pulled, not shipped)

| Ollama tag            | Upstream license | Approx. size (Q4) | Verified |
|-----------------------|------------------|-------------------|----------|
| `phi3.5:3.8b`         | MIT (Microsoft)  | ~2.2 GB           | yes      |
| `qwen2.5:7b-instruct` | Apache-2.0 (Qwen)| ~4.7 GB           | yes      |

Rejected for this spike: Llama 3.1 (Llama Community License is not OSI-approved).

## Explicitly forbidden

- PyMuPDF (AGPL)
- Paid APIs (OpenAI, Anthropic, etc.)
- Automating ChatGPT / Cursor websites as an inference source
