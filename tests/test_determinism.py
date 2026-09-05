"""§4.8 — same input, byte-identical result.

Phase 2 scope: ingesting the same fixture dataset into two independent, fresh
databases must produce identical persisted content in the four source tables
(the `audit_log`'s wall-clock timestamps are the one deliberate exception —
they are never surfaced in `results.json`, per §18's record `audit` shape,
which carries only stage/action/detail).
"""

from __future__ import annotations

from recon.adapters.fixture import FixtureAdapter
from recon.ingest import ingest
from tests.conftest import make_db

_TABLES = ["orders", "recon_lines", "bank_txns", "ledger_entries"]


def _snapshot(conn) -> dict[str, list[tuple]]:
    return {
        table: [tuple(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY record_key")]
        for table in _TABLES
    }


def test_two_independent_ingests_of_the_same_fixture_are_identical() -> None:
    adapter_a = FixtureAdapter(run_id="clean-august")
    adapter_b = FixtureAdapter(run_id="clean-august")

    db_a = make_db()
    db_b = make_db()
    try:
        report_a = ingest(adapter_a, db_a)
        report_b = ingest(adapter_b, db_b)

        assert report_a.model_dump() == report_b.model_dump()
        assert _snapshot(db_a) == _snapshot(db_b)
    finally:
        db_a.close()
        db_b.close()


def test_two_independent_ingests_of_synthetic_rows_are_identical() -> None:
    from tests.conftest import MockAdapter

    order = {
        "order_id": "order_det0000000001",
        "receipt": "RCPT-DET",
        "customer_id": "cust_det0000000001",
        "amount": 55500,
        "currency": "INR",
        "status": "paid",
        "created_at": 1_780_000_000,
        "notes": {},
    }
    db_a = make_db()
    db_b = make_db()
    try:
        ingest(MockAdapter(orders=[order]), db_a)
        ingest(MockAdapter(orders=[order]), db_b)
        assert _snapshot(db_a) == _snapshot(db_b)
    finally:
        db_a.close()
        db_b.close()
