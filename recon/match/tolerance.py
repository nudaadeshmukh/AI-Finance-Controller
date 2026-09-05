"""Pass 6 — `tolerance` — §13.6.

Two of the three allowances are handled elsewhere by construction:
- The derived-fee amount delta (≤2 paise per derived line) is applied
  automatically by `verify()` for ANY caller, based on how many member
  payments needed slab-derivation — not something this pass turns on.
- The ledger posting lag (≤1 day) is `timing.py`'s
  `_attach_orphaned_ledger_entries()`.

This pass's own job is the UTR suffix truncation allowance: a bank
description missing up to `UTR_TRUNCATION_DIGITS` trailing digits of the true
settlement UTR (an observed formatting defect, §8.4). Matches only on a
UNIQUE prefix — a truncated UTR matching two settlements is ambiguity, not a
match, and is left for `classify_residual` / `NO_CANDIDATE`.
"""

from __future__ import annotations

import sqlite3

from recon.db import queries
from recon.match.constants import UTR_TRUNCATION_DIGITS
from recon.match.exact import build_settlement_proposal
from recon.match.utr import extract_utr
from recon.models.pipeline import CascadeState, MatchProposal


class TolerancePass:
    name = "tolerance"

    def run(self, db: sqlite3.Connection, state: CascadeState) -> list[MatchProposal]:
        recon_utrs = {
            row["settlement_utr"]
            for row in db.execute(queries.SELECT_DISTINCT_RECON_SETTLEMENT_UTRS)
        }

        for bank_key in list(state.unmatched_bank):
            row = db.execute(queries.SELECT_BANK_TXN_BY_KEY, {"record_key": bank_key}).fetchone()
            if row is None or row["credit"] <= 0:
                continue
            candidate = extract_utr(row["description"])
            if candidate is None or candidate in recon_utrs:
                continue  # nothing to extract, or already exactly indexed by utr (pass 1)

            matches = [
                utr
                for utr in recon_utrs
                if utr.startswith(candidate)
                and 1 <= len(utr) - len(candidate) <= UTR_TRUNCATION_DIGITS
            ]
            if len(matches) == 1:
                state.derived.utr_index[matches[0]] = bank_key
            # 0 matches: nothing to index, falls through to NO_CANDIDATE.
            # >=2 matches: ambiguity, not a match — requires unique prefix.

        proposals: list[MatchProposal] = []
        for utr, bank_key in list(state.derived.utr_index.items()):
            if bank_key not in state.unmatched_bank:
                continue
            proposal = build_settlement_proposal(
                db, state, utr, bank_key, self.name, require_refund_or_adjustment=None
            )
            if proposal is not None:
                proposals.append(proposal)
        return proposals
