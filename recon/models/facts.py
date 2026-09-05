"""`DerivedFacts` and `FeeSlab` — §20.2.

Everything in `DerivedFacts` is derived from observed data during the cascade,
never imported from `recon/generate/`. It is the structural guarantee behind
the generator/matcher firewall (§4.2, PROJECT_RULES.md rule 2) — the *type* of the
channel a pass uses to share what it learned admits no other source.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from recon.models.types import RecordKey


class FeeSlab(BaseModel):
    """One inferred fee rate for one payment method over one period — §13.4."""

    method: str
    period_start: date
    period_end: date
    inferred_bps: int
    gst_bps: int  # derived from observed (fee, tax) pairs, never hardcoded (C-018/R-1)
    sample_size: int
    reproduces_all_stated: bool  # False ⇒ slab MUST be rejected, never used


class DerivedFacts(BaseModel):
    """Everything the cascade has learned from observed data so far."""

    fee_slabs: list[FeeSlab] = []
    business_days: set[date] = set()
    inferred_holidays: set[date] = set()
    utr_index: dict[str, RecordKey] = {}
    calendar_confidence: float = 0.0
