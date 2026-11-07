"""Earned auto-submit. Default is Mode B: fill, user clicks Submit."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from autoapply.storage.schema import SitePolicyRow


class SubmitGate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed: bool
    reasons: list[str] = Field(default_factory=list)


def can_auto_submit(
    policy: SitePolicyRow,
    *,
    all_required_from_verified: bool,
    has_unreviewed_free_text: bool,
    has_sensitive_without_saved: bool,
    documents_valid: bool,
    is_duplicate: bool,
    captcha_or_wall: bool,
    daily_count: int,
    daily_cap: int = 5,
) -> SubmitGate:
    reasons: list[str] = []
    if policy.mode != "C" or not policy.allow_auto_submit:
        reasons.append("site is not allowlisted for auto-submit (mode B)")
    if not all_required_from_verified:
        reasons.append("required field not from verified profile or answer bank")
    if has_unreviewed_free_text:
        reasons.append("unreviewed free-text answer")
    if has_sensitive_without_saved:
        reasons.append("sensitive question without explicit saved answer")
    if not documents_valid:
        reasons.append("documents failed fact validator")
    if is_duplicate:
        reasons.append("duplicate application")
    if captcha_or_wall:
        reasons.append("CAPTCHA, login wall, or unexpected page")
    if daily_count >= daily_cap:
        reasons.append("daily cap reached")
    return SubmitGate(allowed=len(reasons) == 0, reasons=reasons)
