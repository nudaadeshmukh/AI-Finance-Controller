"""`run_cascade()` and `PASSES` — §13, §20.4.

All six passes, in the fixed, semantically load-bearing order from §13:
`utr`, `exact`, `aggregate`, `fee_reversal`, `timing`, `tolerance`.

`run_cascade()` is the one place cascade-origin proposals are routed through
`verify()`/`commit()` — identical to how the (future) LLM stage's proposals
will be routed, per PROJECT_RULES.md rule 3. After all six passes, `classify_residual`
(§13.7) runs once, converting blanket unresolved residual into specific
reason codes — it matches nothing, so it isn't one of the `PASSES` and isn't
a `PassStat` row.
"""

from __future__ import annotations

import sqlite3
import time

from pydantic import BaseModel

from recon import audit
from recon.db import queries
from recon.db.connection import transaction
from recon.ingest.persist import persist_exception
from recon.match.aggregate import AggregatePass
from recon.match.base import Pass
from recon.match.classify import classify_residual
from recon.match.exact import ExactPass
from recon.match.fee_reversal import FeeReversalPass
from recon.match.timing import TimingPass
from recon.match.tolerance import TolerancePass
from recon.match.utr import UtrPass
from recon.models.facts import DerivedFacts
from recon.models.pipeline import CascadeState
from recon.models.types import RunId
from recon.verify import commit, verify

PASSES: list[Pass] = [
    UtrPass(),
    ExactPass(),
    AggregatePass(),
    FeeReversalPass(),
    TimingPass(),
    TolerancePass(),
]


class PassStat(BaseModel):
    """One row of §19's per-pass CLI table / §18's `passes` array. Counts are
    in terms of recon lines (the scored population), matching §19's
    illustration (`exact 400 138 262 11`), not settlement/group counts.
    """

    model_config = {"extra": "forbid"}

    name: str
    in_count: int = 0
    matched: int = 0
    deferred: int = 0
    runtime_ms: int = 0


class CascadeResult(BaseModel):
    """Return type of `run_cascade()` (§20.4). Fields are provisional, sized
    to what §19's per-pass CLI table and §18's `passes` array need (`PassStat`
    per pass) plus cascade-level totals. `extra="forbid"` so a typo'd field
    fails loudly rather than silently validating.

    Phase 5: `run_id` and `derived` were added so `report/` can assemble
    `results.json` without re-running the cascade — `derived` (the learned
    fee slabs / calendar) is not persisted to any table, and `passes` /
    `runtime_ms` cannot be reconstructed from `audit_log` alone.
    """

    model_config = {"extra": "forbid"}

    run_id: str = ""
    passes: list[PassStat] = []
    total_matched: int = 0
    runtime_ms: int = 0
    derived: DerivedFacts = DerivedFacts()


def _build_initial_state(db: sqlite3.Connection, run_id: RunId) -> CascadeState:
    unmatched_recon = [row["record_key"] for row in db.execute(queries.SELECT_UNMATCHED_RECON_KEYS)]
    unmatched_bank = [row["record_key"] for row in db.execute(queries.SELECT_UNMATCHED_BANK_KEYS)]
    unmatched_ledger = [
        row["record_key"] for row in db.execute(queries.SELECT_UNMATCHED_LEDGER_KEYS)
    ]
    return CascadeState(
        run_id=run_id,
        unmatched_recon=unmatched_recon,
        unmatched_bank=unmatched_bank,
        unmatched_ledger=unmatched_ledger,
        derived=DerivedFacts(),
    )


def _remove_matched_keys(state: CascadeState, member_keys: list[str]) -> int:
    """Removes matched keys from the relevant residual lists. Returns the
    count of *recon* keys removed — that count is what pass_stats reports as
    "matched" (§19's table is in terms of recon lines, not group/member counts).
    """
    matched_recon_count = 0
    for key in member_keys:
        prefix, _, _ = key.partition(":")
        if prefix == "recon" and key in state.unmatched_recon:
            state.unmatched_recon.remove(key)
            matched_recon_count += 1
        elif prefix == "bank" and key in state.unmatched_bank:
            state.unmatched_bank.remove(key)
        elif prefix == "ledger" and key in state.unmatched_ledger:
            state.unmatched_ledger.remove(key)
        # "order" keys have no residual list of their own (§20.2's
        # CascadeState) - their match status is implied by their recon line.
    return matched_recon_count


def run_cascade(
    db: sqlite3.Connection, run_id: RunId, *, passes: list[Pass] = PASSES
) -> CascadeResult:
    """§20.4. Runs `passes` in order over the residual each leaves for the
    next.

    One transaction per pass (§7.2, unchanged for the cascade — only ingest's
    transaction granularity changed, see C-004): a pass's own direct writes
    (e.g. `utr`'s `NOT_A_SETTLEMENT` exceptions) and every proposal it
    produces are verified/committed inside that same transaction, so a pass
    that fails partway never leaves a half-applied result to corrupt the
    next pass's residual. A pass raising is caught at the boundary, logged,
    and marked failed — the cascade continues (§12.3); `state`'s residual
    lists are rebuilt from the database on failure so in-memory state can
    never drift from what was actually committed.
    """
    state = _build_initial_state(db, run_id)
    pass_stats: list[PassStat] = []

    for one_pass in passes:
        # perf_counter, not monotonic: monotonic's ~15ms granularity on Windows
        # quantised sub-15ms pass times to a random 0/15/16ms. perf_counter is
        # the right clock for short durations (Phase 8 measurement).
        start = time.perf_counter()
        in_count = len(state.unmatched_recon)
        matched_count = 0
        try:
            with transaction(db):
                proposals = one_pass.run(db, state)
                for proposal in proposals:
                    proof = verify(proposal, db, state.derived)
                    commit(proposal, proof, db)
                    if proof.closes:
                        matched_count += _remove_matched_keys(state, proposal.member_keys)
        except Exception:  # noqa: BLE001 - a pass failure must not crash the cascade (§12.3)
            matched_count = 0
            state = _rebuild_residual(db, state)
        runtime_ms = int((time.perf_counter() - start) * 1000)
        pass_stats.append(
            PassStat(
                name=one_pass.name,
                in_count=in_count,
                matched=matched_count,
                deferred=len(state.unmatched_recon),
                runtime_ms=runtime_ms,
            )
        )

    with transaction(db):
        for exc in classify_residual(db, state):
            persist_exception(db, exc)
            detail = {"reason_code": exc.reason_code.value, "candidates": exc.candidates}
            audit.record(db, "match.classify", exc.record_key, "classified", detail)

    return CascadeResult(
        run_id=run_id,
        passes=pass_stats,
        total_matched=sum(ps.matched for ps in pass_stats),
        runtime_ms=sum(ps.runtime_ms for ps in pass_stats),
        derived=state.derived,
    )


def _rebuild_residual(db: sqlite3.Connection, state: CascadeState) -> CascadeState:
    """After a failed pass's transaction rolls back, re-derive the residual
    lists from the database rather than trust in-memory mutations made
    before the exception — the DB is the source of truth for what actually
    committed. `state.derived` (DerivedFacts) is left as-is: it isn't
    persisted, and a partially-enriched value is low-risk to reuse.
    """
    fresh = _build_initial_state(db, state.run_id)
    state.unmatched_recon = fresh.unmatched_recon
    state.unmatched_bank = fresh.unmatched_bank
    state.unmatched_ledger = fresh.unmatched_ledger
    return state
