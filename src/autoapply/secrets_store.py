"""Tenant passwords in the OS keychain. Never SQLite, logs, or LLM prompts."""

from __future__ import annotations

import secrets

SERVICE = "autoapply-ai"


def generate_tenant_password() -> str:
    return secrets.token_urlsafe(18)


def store_tenant_password(domain: str, password: str) -> None:
    import keyring

    keyring.set_password(SERVICE, domain, password)
    _remember_domain(domain)


def load_tenant_password(domain: str) -> str | None:
    import keyring

    return keyring.get_password(SERVICE, domain)


def list_credential_domains() -> list[str]:
    path = _domain_index()
    if not path.is_file():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def export_credentials() -> list[dict[str, str]]:
    """Return domain + keychain password for the user's own recovery export."""
    rows: list[dict[str, str]] = []
    for domain in list_credential_domains():
        rows.append({"domain": domain, "password": load_tenant_password(domain) or ""})
    return rows


def _domain_index():
    from autoapply.paths import PROFILE_DIR, ensure_data_dirs

    ensure_data_dirs()
    return PROFILE_DIR / "credential_domains.txt"


def _remember_domain(domain: str) -> None:
    path = _domain_index()
    names = set(list_credential_domains())
    names.add(domain.strip().lower())
    path.write_text("\n".join(sorted(names)) + "\n", encoding="utf-8")
