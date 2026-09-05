"""C-006 regression, protected test (PROJECT_RULES.md, §25).

39/39 tests passed while the entire cascade silently wrote nothing durable —
`verify()`/`commit()` and `UtrPass`'s direct writes had no surrounding
transaction/commit, and every existing test asserted against the SAME
long-lived open connection that wrote the data, so SQLite's own read-your-
uncommitted-writes consistency masked the bug completely. A real CLI
invocation opens a connection, writes, and closes it; a later invocation
opens a brand-new connection to the same file. This test is the automated
version of that cycle — it must run against a real file on disk, never
`:memory:`, and must close the writing connection before reopening.

Never skip, weaken, or xfail this file (PROJECT_RULES.md, §25) — the whole point is
that "the tests are green" must not be able to mean "the database is empty"
ever again.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from recon.db.connection import connect
from recon.ingest import ingest
from recon.match import run_cascade
from tests.conftest import MockAdapter

_ORDER = {
    "order_id": "order_persist00000001",
    "receipt": "RCPT-PERSIST-0001",
    "customer_id": "cust_persist0000001",
    "amount": 100000,
    "currency": "INR",
    "status": "paid",
    "created_at": 1_780_000_000,
    "notes": {},
}

# fee=1800, tax=324 -> expected_net = 100000 - 1800 - 324 = 97876
_RECON_LINE = {
    "entity_id": "pay_persist0000001",
    "type": "payment",
    "debit": 0,
    "credit": 97876,
    "amount": 100000,
    "currency": "INR",
    "fee": 1800,
    "tax": 324,
    "on_hold": False,
    "settled": True,
    "created_at": 1_780_000_000,
    "settled_at": 1_780_100_000,
    "settlement_id": "setl_persist00000001",
    "settlement_utr": "121212121212",
    "order_id": "order_persist00000001",
    "order_receipt": "RCPT-PERSIST-0001",
    "method": "card",
    "description": "Card payment",
}

_MATCHING_BANK_TXN = {
    "txn_id": "TXN_PERSIST_0001",
    "value_date": "2026-08-01",
    "description": "NEFT CR-RAZORPAY-121212121212",
    "credit": 97876,
    "debit": 0,
    "balance": 5_000_000,
}

_UNRELATED_DEBIT = {
    "txn_id": "TXN_PERSIST_RENT",
    "value_date": "2026-08-02",
    "description": "VENDOR PAYMENT - OFFICE RENT",
    "credit": 0,
    "debit": 25000,
    "balance": 4_975_000,
}


def test_cascade_writes_survive_a_connection_close_and_reopen(tmp_path: Path) -> None:
    """The exact open->write->close->reopen->verify cycle a real CLI
    invocation performs. `run_cascade`'s writes must be readable from a
    brand-new connection to the same file, not just the connection that
    wrote them.
    """
    db_path = tmp_path / "persistence_regression.db"

    # --- Phase A: one process/connection writes, then closes entirely -----
    writer_conn = connect(db_path)
    adapter = MockAdapter(
        orders=[_ORDER],
        recon_lines=[_RECON_LINE],
        bank_txns=[_MATCHING_BANK_TXN, _UNRELATED_DEBIT],
    )
    ingest(adapter, writer_conn)
    cascade_result = run_cascade(writer_conn, "persistence-regression")
    writer_conn.close()  # the exact point C-006's bug discarded everything

    assert cascade_result.total_matched == 1  # sanity: the pass itself worked

    # --- Phase B: a brand-new connection to the same file, nothing reused -
    reader_conn = sqlite3.connect(str(db_path))
    reader_conn.row_factory = sqlite3.Row
    try:
        match_groups = reader_conn.execute("SELECT * FROM match_groups").fetchall()
        group_members = reader_conn.execute("SELECT * FROM group_members").fetchall()
        exceptions = reader_conn.execute("SELECT * FROM exceptions").fetchall()
        audit_rows = reader_conn.execute("SELECT * FROM audit_log").fetchall()
    finally:
        reader_conn.close()

    assert len(match_groups) == 1, "match_groups must survive close/reopen"
    assert match_groups[0]["closes"] == 1

    member_keys = {row["record_key"] for row in group_members}
    assert member_keys == {
        "order:order_persist00000001",
        "recon:pay_persist0000001",
        "bank:TXN_PERSIST_0001",
    }, "group_members must survive close/reopen"

    assert len(exceptions) == 1, "the unrelated debit's NOT_A_SETTLEMENT exception must persist"
    assert exceptions[0]["record_key"] == "bank:TXN_PERSIST_RENT"
    assert exceptions[0]["reason_code"] == "NOT_A_SETTLEMENT"

    assert len(audit_rows) > 0, "audit_log must survive close/reopen"
    actions = {row["action"] for row in audit_rows}
    assert "matched" in actions  # from verify/commit
    assert "excluded" in actions  # from match.utr's direct write


def test_rerunning_against_the_reopened_file_is_still_idempotent(tmp_path: Path) -> None:
    """Not just that data persists, but that a second run (fresh connection,
    same file) doesn't double-count what the first run already committed.
    """
    db_path = tmp_path / "persistence_regression_idempotent.db"

    conn_one = connect(db_path)
    adapter = MockAdapter(
        orders=[_ORDER], recon_lines=[_RECON_LINE], bank_txns=[_MATCHING_BANK_TXN]
    )
    ingest(adapter, conn_one)
    run_cascade(conn_one, "persistence-regression")
    conn_one.close()

    conn_two = connect(db_path)  # brand-new connection, same file
    ingest(adapter, conn_two)
    result_two = run_cascade(conn_two, "persistence-regression")
    match_group_count = conn_two.execute("SELECT COUNT(*) AS n FROM match_groups").fetchone()[0]
    group_member_count = conn_two.execute("SELECT COUNT(*) AS n FROM group_members").fetchone()[0]
    conn_two.close()

    already_matched_msg = "already-matched recon lines are excluded from the residual"
    assert result_two.total_matched == 0, already_matched_msg
    assert match_group_count == 1
    assert group_member_count == 3
