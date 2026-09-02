"""`verify()` and `commit()` — §14, §20.4.

`verify()` is pure: it reads and computes, never writes. `commit()` is the
ONLY function in the codebase that writes `match_groups` (CLAUDE.md rule 3).
Built first in Phase 3, before any cascade pass — a verifier written after
the matcher gets shaped to accept it.

Per §11's lifecycle: a proposal whose proof does not close is REJECTED, not
turned into an exception. Its members return to Unmatched, available to a
later pass or the LLM stage — only cascade+LLM exhaustion (Phase 4's
`classify_residual`, §13.7) turns a still-unmatched record into a permanent
`Exception_`. `commit()` therefore writes nothing to `exceptions` on
rejection; it only records the rejection in `audit_log`, per member, so the
full proof is visible in that record's own audit trail (§16).
"""

from __future__ import annotations

import json
import sqlite3
import time

from recon import audit
from recon.db import queries
from recon.ingest.persist import read_bank_txn, read_ledger_entry, read_order, read_recon_line
from recon.models.facts import DerivedFacts
from recon.models.pipeline import ArithmeticProof, MatchProposal
from recon.models.sources import BankTxn, Order, ReconLine
from recon.verify.arithmetic import compute_closing_equation
from recon.verify.proof import build_proof


def verify(proposal: MatchProposal, db: sqlite3.Connection, facts: DerivedFacts) -> ArithmeticProof:
    """Pure: reads, never writes.

    Re-reads every member from SQLite by `record_key`, recomputes the closing
    equation from source values, and returns a proof. A payment line whose
    `fee`/`tax` is still `None` is resolved here via `facts.fee_slabs`
    (Phase 4's fee-reversal) if a validated slab covers its method and date —
    the DB row itself is never rewritten; only this in-memory copy carries
    the derived values, and only for the duration of this one proof.

    The `match.*` imports below are deliberately local, not module-level:
    `match/__init__.py` imports `verify`/`commit` from this module at ITS
    top level (to route cascade proposals through them, CLAUDE.md rule 3),
    so a module-level import here of anything under `recon.match` would be a
    real circular import — Python must fully execute `match/__init__.py`
    (which needs `recon.verify` to already exist) before any `recon.match.X`
    submodule becomes importable. Deferring to call time breaks the cycle.

    §14.1/C-008: when `proposal.arithmetic_scope` is set, the equation is
    read and summed over THAT (a superset of `member_keys`), not
    `member_keys` alone — but the derived-fee tolerance count (`allowed_delta`,
    §13.6) still only counts derivations belonging to `member_keys`, per its
    "member payment" wording. `scope_only_keys` on the returned proof is the
    set difference, always `[]` when `arithmetic_scope` is `None`.
    """
    from recon.match.base import find_applicable_slab
    from recon.match.constants import AMOUNT_DELTA_PAISE_PER_DERIVED_LINE
    from recon.match.fee_reversal import derive_fee

    member_keys_set = set(proposal.member_keys)
    if proposal.arithmetic_scope is None:
        scope_keys = proposal.member_keys
    else:
        scope_keys = proposal.arithmetic_scope
        if not member_keys_set <= set(scope_keys):
            raise ValueError(
                f"MatchProposal {proposal.group_id!r}: member_keys must be a subset of "
                "arithmetic_scope when arithmetic_scope is set (§14.1)"
            )

    orders: list[Order] = []
    recon_lines: list[ReconLine] = []
    bank_txns: list[BankTxn] = []
    any_missing = False
    derived_count = 0
    has_unresolved_fee = False

    for scope_key in scope_keys:
        prefix, _, _ = scope_key.partition(":")
        if prefix == "order":
            order = read_order(db, scope_key)
            any_missing = any_missing or order is None
            if order is not None:
                orders.append(order)
        elif prefix == "recon":
            line = read_recon_line(db, scope_key)
            any_missing = any_missing or line is None
            if line is not None:
                if line.type == "payment" and (line.fee is None or line.tax is None):
                    slab = find_applicable_slab(facts, line.method, line.created_at)
                    if slab is not None:
                        fee, tax = derive_fee(line.amount, slab)
                        line = line.model_copy(update={"fee": fee, "tax": tax})
                        if scope_key in member_keys_set:
                            derived_count += 1
                    else:
                        has_unresolved_fee = True
                recon_lines.append(line)
        elif prefix == "bank":
            txn = read_bank_txn(db, scope_key)
            any_missing = any_missing or txn is None
            if txn is not None:
                bank_txns.append(txn)
        elif prefix == "ledger":
            # Ledger entries are not part of the closing equation (§13.1);
            # read only to confirm the key resolves to a real row.
            entry = read_ledger_entry(db, scope_key)
            any_missing = any_missing or entry is None
        else:
            any_missing = True

    gross, fees, tax, refunds, expected_net = compute_closing_equation(orders, recon_lines)

    has_exactly_one_bank_txn = len(bank_txns) == 1
    observed_net = bank_txns[0].credit if has_exactly_one_bank_txn else 0
    verifiable = not any_missing and has_exactly_one_bank_txn and not has_unresolved_fee

    # §13.6: a settlement whose payments all carry a STATED fee must close at
    # delta == 0 exactly. Only a DERIVED fee can be off, by at most 1 paise
    # each on fee and tax (independent half-up rounding) - so the allowance
    # scales strictly with how many member payments were actually derived,
    # never a flat per-settlement constant.
    allowed_delta = AMOUNT_DELTA_PAISE_PER_DERIVED_LINE * derived_count

    scope_only_keys = sorted(set(scope_keys) - member_keys_set)

    return build_proof(
        gross,
        fees,
        tax,
        refunds,
        expected_net,
        observed_net,
        verifiable=verifiable,
        allowed_delta=allowed_delta,
        scope_only_keys=scope_only_keys,
    )


def commit(proposal: MatchProposal, proof: ArithmeticProof, db: sqlite3.Connection) -> None:
    """THE ONLY WRITER of `match_groups`. No confidence threshold, no
    override flag, no fast path — `proof.closes` is the sole gate.

    §14.1/C-008: `proof.scope_only_keys` are counted in `proof` but never
    written to `group_members` — a plain `"matched"` audit entry for one
    would be false. Each instead gets its own `"counted_not_committed"`
    entry, in addition to (never instead of) the per-member entries below,
    so `audit.trail(key)` shows the connection without anyone needing to
    cross-reference `match_groups.proof_json` by hand.
    """
    detail = {
        "pass_name": proposal.pass_name,
        "origin": proposal.origin,
        "group_id": proposal.group_id,
        "proof": proof.model_dump(),
    }

    if not proof.closes:
        for member_key in proposal.member_keys:
            audit.record(db, "verify", member_key, "rejected", detail)
        return

    db.execute(
        queries.UPSERT_MATCH_GROUP,
        {
            "group_id": proposal.group_id,
            "pass_name": proposal.pass_name,
            "origin": proposal.origin,
            "proof_json": json.dumps(detail["proof"], sort_keys=True),
            "closes": 1,
            "created_at": int(time.time()),
        },
    )
    for member_key in proposal.member_keys:
        db.execute(
            queries.UPSERT_GROUP_MEMBER,
            {"group_id": proposal.group_id, "record_key": member_key},
        )
        # A record cannot be simultaneously matched and an exception
        # (CLAUDE.md rule 4) — clear any stale exception from an earlier run.
        db.execute(queries.DELETE_EXCEPTION_BY_KEY, {"record_key": member_key})
        audit.record(db, "verify", member_key, "matched", detail)

    for scope_only_key in proof.scope_only_keys:
        audit.record(db, "verify", scope_only_key, "counted_not_committed", detail)
