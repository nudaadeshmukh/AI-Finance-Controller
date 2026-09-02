"""§4.8 — same input, byte-identical result. Re-running the pipeline never
double-counts — all writes are upserts on `record_key`.

Phase 2 scope: `ingest()` run twice against the same database, same input,
must not double the row counts.
"""

from __future__ import annotations

import sqlite3

from recon.ingest import ingest
from tests.conftest import MockAdapter


def test_ingesting_twice_does_not_duplicate_rows(
    db: sqlite3.Connection, one_valid_order: dict
) -> None:
    adapter = MockAdapter(orders=[one_valid_order])

    first = ingest(adapter, db)
    second = ingest(adapter, db)

    assert first.orders == second.orders == 1
    assert db.execute("SELECT COUNT(*) AS n FROM orders").fetchone()["n"] == 1


def test_ingesting_twice_with_updated_field_overwrites_not_appends(db: sqlite3.Connection) -> None:
    order_v1 = {
        "order_id": "order_idem0000000001",
        "receipt": "RCPT-OLD",
        "customer_id": "cust_test0000000001",
        "amount": 100000,
        "currency": "INR",
        "status": "paid",
        "created_at": 1_780_000_000,
        "notes": {},
    }
    order_v2 = dict(order_v1, receipt="RCPT-NEW", amount=200000)

    ingest(MockAdapter(orders=[order_v1]), db)
    ingest(MockAdapter(orders=[order_v2]), db)

    rows = db.execute("SELECT * FROM orders").fetchall()
    assert len(rows) == 1
    assert rows[0]["receipt"] == "RCPT-NEW"
    assert rows[0]["amount"] == 200000


def test_ingesting_twice_does_not_duplicate_malformed_exceptions(db: sqlite3.Connection) -> None:
    bad_order = {"currency": "INR"}  # missing required fields -> same positional key both times
    adapter = MockAdapter(orders=[bad_order])

    ingest(adapter, db)
    ingest(adapter, db)

    assert db.execute("SELECT COUNT(*) AS n FROM exceptions").fetchone()["n"] == 1


def test_ingesting_all_four_sources_twice_matches_the_frozen_fixture() -> None:
    """A closer-to-real check using the actual clean-august fixture files
    (read-only; nothing here writes back to data/).
    """
    from recon.adapters.fixture import FixtureAdapter

    adapter = FixtureAdapter(run_id="clean-august")
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    from recon.db.connection import apply_schema

    apply_schema(conn)

    first = ingest(adapter, conn)
    second = ingest(adapter, conn)

    assert first.orders == second.orders
    assert first.recon_lines == second.recon_lines == 400
    assert first.bank_txns == second.bank_txns
    assert first.ledger_entries == second.ledger_entries
    assert conn.execute("SELECT COUNT(*) AS n FROM recon_lines").fetchone()["n"] == 400
    conn.close()
