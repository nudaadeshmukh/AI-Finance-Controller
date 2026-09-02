"""`classify_residual` — assigns specific reason codes after the cascade,
before the LLM stage — §13.7. `classify_residual` itself is Phase 4 scope.

`has_ambiguous_adjustment()` was pulled forward into Phase 3, a phase early,
acknowledged as a deliberate exception to "do not build ahead": running
`aggregate` (§13.3) against the real frozen datasets surfaced a confirmed
false match — the settlement-level closing equation balances regardless of
which candidate order an ambiguous adjustment "really" belongs to, so
`aggregate` was closing groups containing one, with no per-order attribution
needed for the arithmetic to succeed. See `docs/challenges-log.md` C-005 for
the two confirmed instances and how they were verified without opening the
sealed answer key.

This function implements ONLY §13.7's detection *condition* — no reason
code, no candidate list, no `Exception_` construction. `aggregate.py` calls
it purely as a skip guard (defer, don't classify). Phase 4's
`classify_residual` will import and reuse this same function rather than
re-deriving the condition — one detection implementation, called from two
places at two different phases.
"""

from __future__ import annotations

import sqlite3

from recon.db import queries
from recon.models.pipeline import CascadeState, Exception_
from recon.models.reasons import REASON_LABELS, ReasonCode

_ALL_PASS_NAMES = ["utr", "exact", "aggregate", "fee_reversal", "timing", "tolerance"]


def has_ambiguous_adjustment(db: sqlite3.Connection, settlement_id: str) -> bool:
    """§13.7's detection condition: does this settlement contain an
    `adjustment` line with `order_id IS NULL` (true of every adjustment, by
    construction — §6.2) whose amount matches at least 2 orders that share
    the same `customer_id`, `amount`, and calendar date with each other?

    A pure boolean signal — never decides what to do about it.
    """
    adjustment_rows = db.execute(
        queries.SELECT_ADJUSTMENTS_BY_SETTLEMENT_ID, {"settlement_id": settlement_id}
    ).fetchall()
    for row in adjustment_rows:
        if row["order_id"] is not None:
            continue  # not the ambiguous shape §13.7 describes
        bucket_count = db.execute(
            queries.SELECT_DUPLICATE_ORDER_BUCKET_COUNT, {"amount": row["amount"]}
        ).fetchone()["n"]
        if bucket_count > 0:
            return True
    return False


def _duplicate_order_candidates(db: sqlite3.Connection, amount: int) -> list[str]:
    rows = db.execute(queries.SELECT_DUPLICATE_ORDER_IDS_BY_AMOUNT, {"amount": amount}).fetchall()
    return [row["order_id"] for row in rows]


def classify_residual(db: sqlite3.Connection, state: CascadeState) -> list[Exception_]:
    """§13.7, §20.4. Runs at the end of `run_cascade()`, after pass 6 and
    before the LLM stage. Matches nothing — converts blanket unresolved
    residual into specific, honest reason codes, in priority order:

    1. An unmatched adjustment (`order_id IS NULL`, true of every adjustment
       by construction) whose amount matches >=2 orders sharing
       `customer_id` + `amount` + calendar date -> `AMBIGUOUS_DUPLICATE`,
       listing every such order as a candidate. Never picks one.
    2. An unmatched recon line whose `settlement_utr` was never indexed by
       either `utr` or `tolerance` (no bank transaction was ever found for
       it) -> `CROSS_PERIOD_UTR`.
    3. Everything else still unresolved -> `NO_CANDIDATE`.
    """
    exceptions: list[Exception_] = []

    for record_key in list(state.unmatched_recon):
        row = db.execute(queries.SELECT_RECON_LINE_BY_KEY, {"record_key": record_key}).fetchone()
        if row is None:
            continue

        if row["type"] == "adjustment" and row["order_id"] is None:
            candidates = _duplicate_order_candidates(db, row["amount"])
            if len(candidates) >= 2:
                exceptions.append(
                    Exception_(
                        record_key=record_key,
                        reason_code=ReasonCode.AMBIGUOUS_DUPLICATE,
                        reason_text=REASON_LABELS[ReasonCode.AMBIGUOUS_DUPLICATE],
                        passes_tried=_ALL_PASS_NAMES,
                        candidates=[f"order:{order_id}" for order_id in candidates],
                    )
                )
                continue

        utr = row["settlement_utr"]
        if utr is None or utr not in state.derived.utr_index:
            exceptions.append(
                Exception_(
                    record_key=record_key,
                    reason_code=ReasonCode.CROSS_PERIOD_UTR,
                    reason_text=REASON_LABELS[ReasonCode.CROSS_PERIOD_UTR],
                    passes_tried=_ALL_PASS_NAMES,
                    candidates=[],
                )
            )
            continue

        exceptions.append(
            Exception_(
                record_key=record_key,
                reason_code=ReasonCode.NO_CANDIDATE,
                reason_text=REASON_LABELS[ReasonCode.NO_CANDIDATE],
                passes_tried=_ALL_PASS_NAMES,
                candidates=[],
            )
        )

    return exceptions
