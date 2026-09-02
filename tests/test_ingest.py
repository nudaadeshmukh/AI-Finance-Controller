"""§12.2 — malformed rows are recorded as exceptions, never raised."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator

import pytest

from recon.errors import SourceUnavailable
from recon.ingest import ingest
from tests.conftest import MockAdapter

_SOURCE_TABLES = ("orders", "recon_lines", "bank_txns", "ledger_entries")


def test_valid_rows_are_ingested(db: sqlite3.Connection, one_valid_order: dict) -> None:
    adapter = MockAdapter(orders=[one_valid_order])
    report = ingest(adapter, db)

    assert report.orders == 1
    assert report.malformed == 0
    row = db.execute("SELECT * FROM orders").fetchone()
    assert row["order_id"] == "order_test0000000001"
    assert row["amount"] == 100000


def test_malformed_row_does_not_raise_and_is_recorded(
    db: sqlite3.Connection, one_valid_order: dict
) -> None:
    malformed = dict(one_valid_order)
    malformed["order_id"] = "order_bad0000000001"
    malformed["amount"] = "not-a-number"  # invalid type -> pydantic ValidationError

    adapter = MockAdapter(orders=[one_valid_order, malformed])

    # Must not raise.
    report = ingest(adapter, db)

    assert report.orders == 1  # only the valid row persisted
    assert report.malformed == 1

    exc_row = db.execute(
        "SELECT * FROM exceptions WHERE record_key = ?", ("order:order_bad0000000001",)
    ).fetchone()
    assert exc_row is not None
    assert exc_row["reason_code"] == "MALFORMED_SOURCE_ROW"

    # The valid row alongside it still made it into orders.
    assert db.execute("SELECT COUNT(*) AS n FROM orders").fetchone()["n"] == 1


def test_malformed_row_missing_id_field_gets_a_positional_key(db: sqlite3.Connection) -> None:
    adapter = MockAdapter(orders=[{"currency": "INR"}])  # missing almost everything
    report = ingest(adapter, db)

    assert report.orders == 0
    assert report.malformed == 1
    exc_row = db.execute("SELECT * FROM exceptions").fetchone()
    assert exc_row["record_key"] == "order:MALFORMED-0"


def test_ingest_processes_all_four_sources(db: sqlite3.Connection, one_valid_order: dict) -> None:
    recon_line = {
        "entity_id": "pay_test0000000001",
        "type": "payment",
        "debit": 0,
        "credit": 98200,
        "amount": 100000,
        "currency": "INR",
        "fee": 1800,
        "tax": 0,
        "on_hold": False,
        "settled": True,
        "created_at": 1_780_000_000,
        "settled_at": 1_780_100_000,
        "settlement_id": "setl_test0000000001",
        "settlement_utr": "123456789012",
        "order_id": "order_test0000000001",
        "order_receipt": "RCPT-TEST-0001",
        "method": "card",
        "description": "Card payment",
    }
    bank_txn = {
        "txn_id": "TXN0001",
        "value_date": "2026-08-01",
        "description": "NEFT CR-RAZORPAY-123456789012",
        "credit": 98200,
        "debit": 0,
        "balance": 1000000,
    }
    ledger_entry = {
        "entry_id": "JE-TEST-0001",
        "entry_date": "2026-08-01",
        "account": "revenue",
        "debit": 0,
        "credit": 100000,
        "narration": "Web order revenue",
        "source_ref": "RCPT-TEST-0001",
    }
    adapter = MockAdapter(
        orders=[one_valid_order],
        recon_lines=[recon_line],
        bank_txns=[bank_txn],
        ledger_entries=[ledger_entry],
    )

    report = ingest(adapter, db)

    assert (report.orders, report.recon_lines, report.bank_txns, report.ledger_entries) == (
        1,
        1,
        1,
        1,
    )
    assert db.execute("SELECT COUNT(*) AS n FROM recon_lines").fetchone()["n"] == 1
    assert db.execute("SELECT COUNT(*) AS n FROM bank_txns").fetchone()["n"] == 1
    assert db.execute("SELECT COUNT(*) AS n FROM ledger_entries").fetchone()["n"] == 1
    # bank_txns.utr_extracted stays NULL at ingest — match/utr.py populates it (Phase 3).
    assert db.execute("SELECT utr_extracted FROM bank_txns").fetchone()["utr_extracted"] is None


def test_ingest_writes_audit_trail(db: sqlite3.Connection, one_valid_order: dict) -> None:
    adapter = MockAdapter(orders=[one_valid_order])
    ingest(adapter, db)

    rows = db.execute("SELECT * FROM audit_log WHERE stage = 'ingest'").fetchall()
    assert len(rows) >= 1
    assert any(row["action"] == "ingested" for row in rows)


class _KillSwitchAdapter:
    """A `SourceAdapter` that succeeds on the first two sources (`orders`,
    `recon_lines`) and raises `SourceUnavailable` on the third
    (`bank_txns`) — simulating acquisition failing partway through §12.1's
    four-source sequence.
    """

    def __init__(self, one_valid_order: dict) -> None:
        self._order = one_valid_order

    def orders(self) -> Iterator[dict]:
        return iter([self._order])

    def recon_lines(self) -> Iterator[dict]:
        return iter([])  # empty is a valid, successful source

    def bank_txns(self) -> Iterator[dict]:
        raise SourceUnavailable("simulated failure on source 3 of 4")

    def ledger_entries(self) -> Iterator[dict]:
        return iter([])


def test_source_unavailable_partway_through_leaves_no_partial_write(
    db: sqlite3.Connection, one_valid_order: dict
) -> None:
    """§12.1: SourceUnavailable -> exit 2, no partial write — not even from
    sources that "succeeded" internally before the failing one, within the
    same `ingest()` call (§7.2 deviation noted in `ingest/__init__.py`).
    """
    adapter = _KillSwitchAdapter(one_valid_order)

    with pytest.raises(SourceUnavailable):
        ingest(adapter, db)

    for table in _SOURCE_TABLES:
        count = db.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
        assert count == 0, f"{table} has {count} row(s) after a partial failure"

    # The rolled-back transaction also takes its audit_log writes with it.
    assert db.execute("SELECT COUNT(*) AS n FROM audit_log").fetchone()["n"] == 0
