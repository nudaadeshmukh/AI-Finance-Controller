"""The `Pass` protocol every cascade pass implements — §13.

`find_applicable_slab` lives here (not in `fee_reversal.py`, where it's
described in §20.4) because both `fee_reversal.py` (deriving fee/tax) and
`exact.py` (deciding whether a fee-null settlement is even worth attempting)
need it, and `fee_reversal.py` already imports from `exact.py` — putting it
there would create a cycle. `base.py` has no dependents of its own within
`match/`, so it's the natural shared, dependency-free home.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import Protocol

from recon.models.facts import DerivedFacts, FeeSlab
from recon.models.pipeline import CascadeState, MatchProposal


class Pass(Protocol):
    name: str

    def run(self, db: sqlite3.Connection, state: CascadeState) -> list[MatchProposal]: ...


def find_applicable_slab(facts: DerivedFacts, method: str, created_at: int) -> FeeSlab | None:
    """The slab (if any) covering `method` on the calendar date `created_at`
    falls on — §13.4. Shared by `verify()` (to resolve a null-fee line's
    arithmetic) and `build_settlement_proposal` (to decide whether a
    fee-null settlement is even worth attempting).
    """
    day = datetime.fromtimestamp(created_at, tz=UTC).date()
    for slab in facts.fee_slabs:
        if slab.method == method and slab.period_start <= day <= slab.period_end:
            return slab
    return None
