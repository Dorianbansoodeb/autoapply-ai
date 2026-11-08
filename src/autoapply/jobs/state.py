"""Job state machine. Illegal jumps are rejected; submit is never retried from uncertain."""

from __future__ import annotations

JOB_STATES = frozenset(
    {
        "new",
        "rejected",
        "eligible",
        "documents_ready",
        "in_progress",
        "submitted_by_user",
        "uncertain",
        "closed",
        "duplicate",
        "expired",
        "blocked_by_policy",
    }
)

JOB_TRANSITIONS: dict[str, frozenset[str]] = {
    "new": frozenset(
        {"rejected", "eligible", "duplicate", "expired", "blocked_by_policy", "closed"}
    ),
    "eligible": frozenset({"documents_ready", "rejected", "closed", "blocked_by_policy"}),
    "documents_ready": frozenset({"in_progress", "closed"}),
    "in_progress": frozenset({"submitted_by_user", "uncertain", "closed"}),
    "submitted_by_user": frozenset({"closed"}),
    "uncertain": frozenset({"closed"}),
    "duplicate": frozenset({"closed"}),
    "expired": frozenset({"closed"}),
    "blocked_by_policy": frozenset({"closed"}),
    "rejected": frozenset({"closed"}),
    "closed": frozenset(),
}

FORM_TRANSITIONS: dict[str, frozenset[str]] = {
    "opened": frozenset(
        {"filling", "needs_input", "ready_for_review", "submitting", "uncertain", "blocked"}
    ),
    "filling": frozenset(
        {"needs_input", "ready_for_review", "submitting", "uncertain", "blocked"}
    ),
    "needs_input": frozenset({"filling", "ready_for_review", "uncertain", "blocked"}),
    "ready_for_review": frozenset({"submitting", "needs_input", "uncertain", "submitted"}),
    "submitting": frozenset({"uncertain", "submitted", "verified"}),
    "submitted": frozenset({"verified", "uncertain"}),
    "verified": frozenset(),
    "uncertain": frozenset({"closed"}),
    "blocked": frozenset({"needs_input", "uncertain"}),
    "closed": frozenset(),
}


class IllegalTransition(ValueError):
    pass


def transition(current: str, nxt: str, table: dict[str, frozenset[str]]) -> str:
    if nxt == current:
        return current
    allowed = table.get(current)
    if allowed is None or nxt not in allowed:
        raise IllegalTransition(f"cannot move {current} → {nxt}")
    return nxt
