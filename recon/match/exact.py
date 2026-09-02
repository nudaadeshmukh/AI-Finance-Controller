"""Pass 2 — `exact` — §13.3.

For each UTR indexed by pass 1, collects that settlement's recon lines, joins
orders via `order_id`, and proposes a closure with **stated** fee/tax only.
Handles pure-payment settlements — no refund/adjustment lines (that's
`aggregate`'s job) — and skips any settlement containing a payment with
`fee IS NULL` that no derived slab covers yet (`fee_reversal`, Phase 4).

`build_settlement_proposal` is shared by `exact`, `aggregate` and
`fee_reversal` — the `require_refund_or_adjustment` flag is how the three
differ: `False` (exact), `True` (aggregate), `None` (fee_reversal — attempt
the settlement regardless of composition, now that fees may be derivable).
"""

from __future__ import annotations

import sqlite3

from recon.db import queries
from recon.match.base import find_applicable_slab
from recon.match.classify import has_ambiguous_adjustment
from recon.models.pipeline import CascadeState, MatchProposal


def group_id_for_settlement(recon_rows: list[sqlite3.Row], utr: str) -> str:
    """`grp_<settlement>` per §13.1 — the 8 characters following `setl_` in
    the group's `settlement_id`, matching the convention observed in the
    frozen answer keys. Falls back to the UTR's own prefix if a row is
    somehow missing `settlement_id` (defensive; not expected in practice).
    """
    settlement_id = next((row["settlement_id"] for row in recon_rows if row["settlement_id"]), None)
    if settlement_id and len(settlement_id) >= 13:
        return f"grp_{settlement_id[5:13]}"
    return f"grp_{utr[:8]}"


def build_settlement_proposal(
    db: sqlite3.Connection,
    state: CascadeState,
    utr: str,
    bank_key: str,
    pass_name: str,
    *,
    require_refund_or_adjustment: bool | None,
) -> MatchProposal | None:
    """Shared by `exact`, `aggregate` and `fee_reversal`: gather the
    settlement's recon lines for `utr`, apply the fee-null skip and the
    refund/adjustment split, and build one `MatchProposal` for the whole
    settlement (§13.1: a reconciliation group is one settlement). Returns
    `None` if this UTR isn't this pass's responsibility right now.
    """
    rows = db.execute(
        queries.SELECT_RECON_LINES_BY_SETTLEMENT_UTR, {"settlement_utr": utr}
    ).fetchall()
    if not rows:
        return None

    recon_keys = [row["record_key"] for row in rows]
    if not all(key in state.unmatched_recon for key in recon_keys):
        return None  # partially or fully already matched — not this pass's job

    if require_refund_or_adjustment is not None:
        has_refund_or_adjustment = any(row["type"] in ("refund", "adjustment") for row in rows)
        if has_refund_or_adjustment != require_refund_or_adjustment:
            return None  # exact wants none; aggregate wants at least one

    for row in rows:
        if row["type"] != "payment" or row["fee"] is not None:
            continue
        # A null fee is only worth attempting once a derived slab covers it
        # (fee_reversal, Phase 4) — never guess a rate here. Before any slab
        # exists (exact/aggregate), this always defers.
        if find_applicable_slab(state.derived, row["method"], row["created_at"]) is None:
            return None

    settlement_id = next((row["settlement_id"] for row in rows if row["settlement_id"]), None)
    if settlement_id and has_ambiguous_adjustment(db, settlement_id):
        # The equation would still close (it doesn't need per-order
        # attribution), but that would be a false match on the ambiguous
        # adjustment specifically — defer the whole settlement instead.
        # classify_residual (Phase 4) picks this up and names it properly.
        return None

    # Never attribute an adjustment to an order — adjustments carry
    # order_id = NULL by construction (§13.3). Only include orders actually
    # referenced by a member recon line.
    order_ids = sorted({row["order_id"] for row in rows if row["order_id"] is not None})

    member_keys = [bank_key, *recon_keys, *[f"order:{order_id}" for order_id in order_ids]]
    return MatchProposal(
        group_id=group_id_for_settlement(rows, utr),
        member_keys=member_keys,
        pass_name=pass_name,
        origin="cascade",
    )


class ExactPass:
    name = "exact"

    def run(self, db: sqlite3.Connection, state: CascadeState) -> list[MatchProposal]:
        proposals: list[MatchProposal] = []
        for utr, bank_key in list(state.derived.utr_index.items()):
            if bank_key not in state.unmatched_bank:
                continue
            proposal = build_settlement_proposal(
                db, state, utr, bank_key, self.name, require_refund_or_adjustment=False
            )
            if proposal is not None:
                proposals.append(proposal)
        return proposals
