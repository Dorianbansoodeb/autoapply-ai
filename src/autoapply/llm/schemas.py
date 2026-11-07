"""Pydantic schemas for Milestone 0 model calls."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class FreeTextDraft(BaseModel):
    """Draft answer for a free-text application question.

    Always treated as needing human review in Milestone 0.
    """

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(description="Draft text using only the provided facts.")
    cited_fact_ids: list[str] = Field(
        default_factory=list,
        description="IDs of candidate facts that support the answer.",
    )
    unsupported: bool = Field(
        default=False,
        description="True if the question cannot be answered from the given facts.",
    )
