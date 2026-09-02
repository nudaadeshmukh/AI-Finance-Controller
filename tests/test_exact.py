"""Pass 2 — `exact` — §13.3."""

from __future__ import annotations

import sqlite3

from recon.ingest import ingest
from recon.match import run_cascade
from tests.conftest import MockAdapter


def _order(order_id: str, amount: int, customer: str = "cust_exact00000001") -> dict:
    return {
        "order_id": order_id,
        "receipt": f"RCPT-{order_id}",
        "customer_id": customer,
        "amount": amount,
        "currency": "INR",
        "status": "paid",
        "created_at": 1_780_000_000,
        "notes": {},
    }


def _payment(
    entity_id: str, order_id: str, utr: str, amount: int, fee: int | None, tax: int | None
) -> dict:
    credit = amount - (fee or 0) - (tax or 0)
    return {
        "entity_id": entity_id,
        "type": "payment",
        "debit": 0,
        "credit": credit,
        "amount": amount,
        "currency": "INR",
        "fee": fee,
        "tax": tax,
        "on_hold": False,
        "settled": True,
        "created_at": 1_780_000_000,
        "settled_at": 1_780_100_000,
        "settlement_id": "setl_exacttestAAAA",
        "settlement_utr": utr,
        "order_id": order_id,
        "order_receipt": f"RCPT-{order_id}",
        "method": "card",
        "description": "Card payment",
    }


def _bank_txn(txn_id: str, utr: str, credit: int) -> dict:
    return {
        "txn_id": txn_id,
        "value_date": "2026-08-01",
        "description": f"NEFT CR-RAZORPAY-{utr}",
        "credit": credit,
        "debit": 0,
        "balance": 1_000_000,
    }


def test_a_pure_payment_settlement_with_stated_fee_is_matched(db: sqlite3.Connection) -> None:
    order = _order("order_exact0000001", 100000)
    payment = _payment("pay_exact00000001", order["order_id"], "111100002222", 100000, 1800, 324)
    bank_txn = _bank_txn("TXN_EXACT_0001", "111100002222", 100000 - 1800 - 324)
    ingest(MockAdapter(orders=[order], recon_lines=[payment], bank_txns=[bank_txn]), db)

    result = run_cascade(db, "test")

    exact_stat = next(ps for ps in result.passes if ps.name == "exact")
    assert exact_stat.matched == 1
    assert db.execute("SELECT COUNT(*) AS n FROM match_groups").fetchone()["n"] == 1


def test_a_multi_payment_settlement_all_stated_fees_closes_as_one_group(
    db: sqlite3.Connection,
) -> None:
    order_a = _order("order_exact0000002", 50000)
    order_b = _order("order_exact0000003", 70000)
    payment_a = _payment("pay_exact00000002", order_a["order_id"], "333300004444", 50000, 900, 162)
    payment_b = _payment("pay_exact00000003", order_b["order_id"], "333300004444", 70000, 1260, 227)
    total_credit = (50000 - 900 - 162) + (70000 - 1260 - 227)
    bank_txn = _bank_txn("TXN_EXACT_0002", "333300004444", total_credit)
    adapter = MockAdapter(
        orders=[order_a, order_b], recon_lines=[payment_a, payment_b], bank_txns=[bank_txn]
    )
    ingest(adapter, db)

    run_cascade(db, "test")

    group_row = db.execute("SELECT * FROM match_groups").fetchone()
    assert group_row is not None
    member_keys = {
        row["record_key"]
        for row in db.execute(
            "SELECT record_key FROM group_members WHERE group_id = ?", (group_row["group_id"],)
        )
    }
    assert member_keys == {
        "bank:TXN_EXACT_0002",
        "recon:pay_exact00000002",
        "recon:pay_exact00000003",
        "order:order_exact0000002",
        "order:order_exact0000003",
    }


def test_a_settlement_with_a_null_fee_line_is_skipped_by_exact(db: sqlite3.Connection) -> None:
    order = _order("order_exact0000004", 100000)
    payment = _payment("pay_exact00000004", order["order_id"], "555500006666", 100000, None, None)
    bank_txn = _bank_txn("TXN_EXACT_0003", "555500006666", 100000)  # UPI-style 0% fee, but unstated
    ingest(MockAdapter(orders=[order], recon_lines=[payment], bank_txns=[bank_txn]), db)

    result = run_cascade(db, "test")

    exact_stat = next(ps for ps in result.passes if ps.name == "exact")
    assert exact_stat.matched == 0
    assert db.execute("SELECT COUNT(*) AS n FROM match_groups").fetchone()["n"] == 0


def test_a_settlement_with_a_refund_is_left_to_aggregate_not_exact(db: sqlite3.Connection) -> None:
    order = _order("order_exact0000005", 100000)
    payment = _payment("pay_exact00000005", order["order_id"], "777788889999", 100000, 1800, 324)
    refund = {
        "entity_id": "rfnd_exact0000005",
        "type": "refund",
        "debit": 20000,
        "credit": 0,
        "amount": 20000,
        "currency": "INR",
        "fee": None,
        "tax": None,
        "on_hold": False,
        "settled": True,
        "created_at": 1_780_000_000,
        "settled_at": 1_780_100_000,
        "settlement_id": "setl_exacttestAAAA",
        "settlement_utr": "777788889999",
        "order_id": order["order_id"],
        "order_receipt": order["receipt"],
        "method": "card",
        "description": "Refund",
    }
    net = (100000 - 1800 - 324) - 20000
    bank_txn = _bank_txn("TXN_EXACT_0004", "777788889999", net)
    ingest(
        MockAdapter(orders=[order], recon_lines=[payment, refund], bank_txns=[bank_txn]),
        db,
    )

    # Only run utr + exact - if exact incorrectly claimed this settlement,
    # match_groups would already be populated here.
    from recon.match.exact import ExactPass
    from recon.match.utr import UtrPass

    result = run_cascade(db, "test", passes=[UtrPass(), ExactPass()])

    exact_stat = next(ps for ps in result.passes if ps.name == "exact")
    assert exact_stat.matched == 0
    assert db.execute("SELECT COUNT(*) AS n FROM match_groups").fetchone()["n"] == 0
