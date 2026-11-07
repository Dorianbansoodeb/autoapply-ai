"""Tenant passwords in the OS keychain. Never SQLite, logs, or LLM prompts."""

from __future__ import annotations

import secrets

SERVICE = "autoapply-ai"


def generate_tenant_password() -> str:
    return secrets.token_urlsafe(18)


def store_tenant_password(domain: str, password: str) -> None:
    import keyring

    keyring.set_password(SERVICE, domain, password)


def load_tenant_password(domain: str) -> str | None:
    import keyring

    return keyring.get_password(SERVICE, domain)
