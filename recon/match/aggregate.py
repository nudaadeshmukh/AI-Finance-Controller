"""Pass 3 — `aggregate` — §13.3.

Same equation as `exact`, for settlements where refunds and/or adjustments
net against payments. Adjustments carry `order_id = NULL` by construction and
contribute to the net with no order member — `build_settlement_proposal`
(shared with `exact`, in `match/exact.py`) never attributes one to an order.

**Do not attempt to attribute an adjustment to an order.** For the 5
ambiguous duplicates this is precisely the trap.
"""

from __future__ import annotations

import sqlite3

from recon.match.exact import build_settlement_proposal
from recon.models.pipeline import CascadeState, MatchProposal


class AggregatePass:
    name = "aggregate"

    def run(self, db: sqlite3.Connection, state: CascadeState) -> list[MatchProposal]:
        proposals: list[MatchProposal] = []
        for utr, bank_key in list(state.derived.utr_index.items()):
            if bank_key not in state.unmatched_bank:
                continue
            proposal = build_settlement_proposal(
                db, state, utr, bank_key, self.name, require_refund_or_adjustment=True
            )
            if proposal is not None:
                proposals.append(proposal)
        return proposals
