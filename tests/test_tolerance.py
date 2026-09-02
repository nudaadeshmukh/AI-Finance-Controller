"""Pass 6 — `tolerance` — §13.6.

Two of the three allowances are tested elsewhere on their own terms: the
derived-fee amount delta in `test_verify.py` (it's `verify()`'s own
behaviour, applied automatically for any caller) and the ledger lag as part
of `timing.py`'s ledger attachment. This file covers the UTR-truncation
allowance specifically — the one genuinely new indexing mechanism `tolerance`
adds — including the "requires a unique prefix match" rule: a truncated UTR
matching two settlements is ambiguity, not a match.
"""

from __future__ import annotations

import sqlite3

from recon.ingest import ingest
from recon.match import run_cascade
from tests.conftest import MockAdapter


def _order(order_id: str, amount: int) -> dict:
    return {
        "order_id": order_id,
        "receipt": f"RCPT-{order_id}",
        "customer_id": "cust_tol0000000001",
        "amount": amount,
        "currency": "INR",
        "status": "paid",
        "created_at": 1_780_000_000,
        "notes": {},
    }


def _payment(entity_id: str, order_id: str, utr: str, amount: int, fee: int, tax: int) -> dict:
    return {
        "entity_id": entity_id,
        "type": "payment",
        "debit": 0,
        "credit": amount - fee - tax,
        "amount": amount,
        "currency": "INR",
        "fee": fee,
        "tax": tax,
        "on_hold": False,
        "settled": True,
        "created_at": 1_780_000_000,
        "settled_at": 1_780_100_000,
        "settlement_id": "setl_toltestAAAAAAAA",
        "settlement_utr": utr,
        "order_id": order_id,
        "order_receipt": f"RCPT-{order_id}",
        "method": "card",
        "description": "Card payment",
    }


def test_a_truncated_utr_with_a_unique_prefix_match_is_resolved(db: sqlite3.Connection) -> None:
    full_utr = "111122223344"  # 12 digits
    truncated = full_utr[:-2]  # last 2 digits dropped, the observed defect

    order = _order("order_tol0000000001", 100000)
    payment = _payment("pay_tol00000001", order["order_id"], full_utr, 100000, 1800, 324)
    bank_txn = {
        "txn_id": "TXN_TOL_0001",
        "value_date": "2026-08-01",
        "description": f"NEFT CR-RAZORPAY-{truncated}",  # bank's copy is truncated
        "credit": 100000 - 1800 - 324,
        "debit": 0,
        "balance": 1_000_000,
    }
    ingest(MockAdapter(orders=[order], recon_lines=[payment], bank_txns=[bank_txn]), db)

    result = run_cascade(db, "test")

    tolerance_stat = next(ps for ps in result.passes if ps.name == "tolerance")
    assert tolerance_stat.matched == 1
    assert db.execute("SELECT COUNT(*) AS n FROM match_groups").fetchone()["n"] == 1


def test_a_truncated_utr_matching_two_settlements_is_ambiguity_not_a_match(
    db: sqlite3.Connection,
) -> None:
    """Two full UTRs share the same truncated prefix - the truncated bank
    credit must NOT be resolved to either; that would be a guess.
    """
    prefix = "555566667788"[:-2]
    full_utr_a = prefix + "01"
    full_utr_b = prefix + "02"

    order_a = _order("order_tol0000000002", 50000)
    order_b = _order("order_tol0000000003", 70000)
    payment_a = _payment("pay_tol00000002", order_a["order_id"], full_utr_a, 50000, 900, 162)
    payment_b = _payment("pay_tol00000003", order_b["order_id"], full_utr_b, 70000, 1260, 227)

    # A real bank txn for settlement A, correctly indexed via exact match.
    bank_a = {
        "txn_id": "TXN_TOL_A",
        "value_date": "2026-08-01",
        "description": f"NEFT CR-RAZORPAY-{full_utr_a}",
        "credit": 50000 - 900 - 162,
        "debit": 0,
        "balance": 500_000,
    }
    # A SECOND bank txn whose description is truncated to the shared prefix -
    # ambiguous between settlement A and B's full UTRs.
    bank_truncated = {
        "txn_id": "TXN_TOL_TRUNCATED",
        "value_date": "2026-08-02",
        "description": f"NEFT CR-RAZORPAY-{prefix}",
        "credit": 70000 - 1260 - 227,
        "debit": 0,
        "balance": 600_000,
    }

    ingest(
        MockAdapter(
            orders=[order_a, order_b],
            recon_lines=[payment_a, payment_b],
            bank_txns=[bank_a, bank_truncated],
        ),
        db,
    )

    run_cascade(db, "test")

    # Settlement A resolved via its own exact bank txn.
    matched_keys = {row["record_key"] for row in db.execute("SELECT record_key FROM group_members")}
    assert "recon:pay_tol00000002" in matched_keys
    # Settlement B's truncated-UTR bank credit is genuinely ambiguous -
    # never resolved by guessing.
    assert "recon:pay_tol00000003" not in matched_keys
    assert "bank:TXN_TOL_TRUNCATED" not in matched_keys


def test_truncation_beyond_the_allowance_is_not_matched(db: sqlite3.Connection) -> None:
    """3 missing digits exceeds UTR_TRUNCATION_DIGITS (2) - must not match,
    even though it would otherwise be a unique prefix. Uses a 14-digit UTR
    (within §5.3's 12-22 char range) so the truncated candidate is still
    >=10 digits and passes `extract_utr`'s own regex - this specifically
    exercises the truncation-length ceiling, not extraction failure.
    """
    full_utr = "99998888776655"  # 14 digits
    over_truncated = full_utr[:-3]  # 11 digits - still extractable

    order = _order("order_tol0000000004", 40000)
    payment = _payment("pay_tol00000004", order["order_id"], full_utr, 40000, 720, 130)
    bank_txn = {
        "txn_id": "TXN_TOL_OVER",
        "value_date": "2026-08-01",
        "description": f"NEFT CR-RAZORPAY-{over_truncated}",
        "credit": 40000 - 720 - 130,
        "debit": 0,
        "balance": 300_000,
    }
    ingest(MockAdapter(orders=[order], recon_lines=[payment], bank_txns=[bank_txn]), db)

    run_cascade(db, "test")

    assert db.execute("SELECT COUNT(*) AS n FROM match_groups").fetchone()["n"] == 0
