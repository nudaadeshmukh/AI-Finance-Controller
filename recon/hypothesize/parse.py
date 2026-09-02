"""Strict JSON → `Hypothesis` — §15.2. Prose is a parse failure. Implemented
in Phase 6.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from recon.models.types import RecordKey


class Hypothesis(BaseModel):
    """§15.2. The LLM's proposal shape — `claimed_arithmetic` has no
    functional purpose; it is compared for logging, never used (§14, §15.2).
    """

    proposed_group: list[RecordKey]
    reasoning: str  # displayed in UI, never acted on
    claimed_arithmetic: dict[str, int]  # compared, NEVER used
    confidence: Literal["low", "medium", "high"]  # displayed, gates nothing
