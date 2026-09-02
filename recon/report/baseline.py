"""`compute_baseline()` — the naive matcher for comparison, §8.3, §20.4.

Naive matcher = exact `order_id` join AND stated fee AND exact UTR AND
settlement net closes with no derivation. Implemented in Phase 5.
"""

from __future__ import annotations

import sqlite3

from pydantic import BaseModel


class BaselineResult(BaseModel):
    """Return type of `compute_baseline()` — fields match §18's `baseline`
    object exactly (`{"name": "exact_id_and_amount", "matched": 0,
    "match_rate": 0.0}`), so this is fully specified, not a guess.
    `extra="forbid"` so a typo'd field fails loudly rather than silently
    validating.
    """

    model_config = {"extra": "forbid"}

    name: str = "exact_id_and_amount"
    matched: int = 0
    match_rate: float = 0.0


def compute_baseline(db: sqlite3.Connection) -> BaselineResult:
    """§20.4. Implemented in Phase 5."""
    raise NotImplementedError
