"""Ingest package aggregator — `ingest()`, §20.4.

Per §7.2: this function wraps all four sources in ONE transaction, not one
per source file. §12.1 requires that a `SourceUnavailable` raised partway
through acquisition leave no partial write — not just from the source that
failed, but from any source already read successfully earlier in the same
call. A per-source transaction scheme cannot give that: by the time source 3
of 4 fails, sources 1-2 are already durably committed, which is a partial
write in every sense that matters. A single outer transaction gives the
guarantee atomically, and unlike deleting already-committed rows after the
fact, never touches data a *different*, already-closed successful `ingest()`
call left behind — only this call's own uncommitted work rolls back.
`audit_log` writes participate in this same enclosing transaction.

Covered by
`tests/test_ingest.py::test_source_unavailable_partway_through_leaves_no_partial_write`.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

from pydantic import BaseModel

from recon import audit
from recon.adapters.base import SourceAdapter
from recon.db.connection import transaction
from recon.ingest.persist import (
    persist_exception,
    upsert_bank_txn,
    upsert_ledger_entry,
    upsert_order,
    upsert_recon_line,
)
from recon.ingest.validate import best_effort_key, validate_row
from recon.models.sources import BankTxn, LedgerEntry, Order, ReconLine


class IngestReport(BaseModel):
    """Return type of `ingest()` (§20.4). Fields are provisional — sized to
    what `cli.py run`'s Rich table needs to print per Phase 2's acceptance
    line (`Ingested: orders 360 · recon_lines 400 · bank_txns 65 ·
    ledger_entries 566`) plus the malformed-row count §12.2 requires be
    recorded, not raised. `extra="forbid"` so a typo'd field fails loudly
    (§4.4/§4.6's whole premise) rather than silently validating. Revise when
    `ingest()` is actually implemented in Phase 2.
    """

    model_config = {"extra": "forbid"}

    orders: int = 0
    recon_lines: int = 0
    bank_txns: int = 0
    ledger_entries: int = 0
    malformed: int = 0  # rows recorded as MALFORMED_SOURCE_ROW exceptions


# (report field name, adapter method name, model class, upsert fn, id field, record_key prefix)
_SOURCE_SPECS: list[tuple[str, str, type[BaseModel], Callable, str, str]] = [
    ("orders", "orders", Order, upsert_order, "order_id", "order"),
    ("recon_lines", "recon_lines", ReconLine, upsert_recon_line, "entity_id", "recon"),
    ("bank_txns", "bank_txns", BankTxn, upsert_bank_txn, "txn_id", "bank"),
    ("ledger_entries", "ledger_entries", LedgerEntry, upsert_ledger_entry, "entry_id", "ledger"),
]


def ingest(adapter: SourceAdapter, db: sqlite3.Connection) -> IngestReport:
    """§20.4. Validates and persists all four sources.

    A malformed row is recorded as a `MALFORMED_SOURCE_ROW` exception and
    ingestion continues — it is never raised (§12.2, CLAUDE.md rule 10).

    The whole call is one transaction (see the module docstring): if any
    source raises `SourceUnavailable` partway through, nothing this call
    touched — not even an earlier source that "succeeded" within the same
    call — remains committed (§12.1).
    """
    report = IngestReport()
    with transaction(db):
        for field_name, method_name, model_cls, upsert_fn, id_field, prefix in _SOURCE_SPECS:
            count = 0
            malformed = 0
            rows = getattr(adapter, method_name)()
            for index, raw in enumerate(rows):
                record_key = best_effort_key(prefix, raw, id_field, index)
                validated, exc = validate_row(model_cls, raw, record_key)
                if exc is not None:
                    persist_exception(db, exc)
                    detail = {"error": exc.reason_text}
                    audit.record(db, "ingest", exc.record_key, "malformed", detail)
                    malformed += 1
                    continue
                upsert_fn(db, validated)
                count += 1
            audit.record(
                db,
                "ingest",
                None,
                "ingested",
                {"source": field_name, "count": count, "malformed": malformed},
            )
            setattr(report, field_name, count)
            report.malformed += malformed
    return report
